"""The wizard's backend: what `POST /cadastre/project` builds, and what it refuses.

The refusals are the point. A project is the one object every later screen reads, so a
wrong setting here is not caught downstream - it is *inherited* downstream, silently, by
every unit the project will ever hold. Each guard below has a mutation in
`tools/mutation_check.py`.
"""

from __future__ import annotations

import json

import pytest
from cadastre.api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

SAMPLES = "sidecar/ingest/test_data"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def parcels(repo_root):
    return str(repo_root / SAMPLES / "sample_parcels.geojson")


@pytest.fixture
def buildings(repo_root):
    return str(repo_root / SAMPLES / "sample_buildings.geojson")


def source(path, source_type="parcel_map", **over):
    s = {
        "path": path, "source_type": source_type, "name": "Ward 42 parcels",
        "provider": "Survey of India", "capture_date": "2026-03-11",
        "crs": "EPSG:4326", "vertical_datum": "EGM2008",
        "horizontal_accuracy_m": 0.30, "vertical_accuracy_m": 0.50,
    }
    s.update(over)
    return s


#: The settings a wizard collects. Spelled out rather than left to defaults, because
#: `ProjectCreateRequest` no longer has any - a CRS and a vertical datum are facts about
#: the operator's data, and a default silently reprojected every project into an Indian
#: UTM zone with nothing downstream able to notice.
PROJECT_DEFAULTS = {
    "project_crs": "EPSG:32643",
    "vertical_datum": "EGM2008",
    "stratum_below_limit_m": -30.0,
    "stratum_above_limit_m": 150.0,
    "default_plinth_offset_m": 0.6,
    "default_parapet_deduction_m": 0.0,
    "ulpin_version": "v1",
    "ruleset_version": "r1",
}


def body(tmp_path, sources, **over):
    b = {"db_path": str(tmp_path / "new.gpkg"), "sources": sources, **PROJECT_DEFAULTS}
    b.update(over)
    return b


def test_creates_a_project_and_imports_it_in_one_call(client, tmp_path, parcels, buildings):
    """Creation and ingest are one call: a project holding no units is not a useful state."""
    r = client.post("/cadastre/project", json=body(
        tmp_path, [source(parcels), source(buildings, "footprint")]))
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["layers"] == ["parcel", "building_footprint"]
    assert got["units"] == 2
    assert got["provisional_ulpins"] == 2
    assert got["relationships"] == 2      # contains + inside, both directions


def test_source_accuracy_is_written_through_to_the_registry(client, tmp_path, parcels):
    """P4's tolerances read this table. The operator's number must arrive intact."""
    import sqlite3
    r = client.post("/cadastre/project", json=body(tmp_path, [
        source(parcels, horizontal_accuracy_m=0.42, vertical_accuracy_m=0.77)]))
    assert r.status_code == 200, r.text
    conn = sqlite3.connect(r.json()["db_path"])
    row = conn.execute("SELECT horizontal_accuracy_m, vertical_accuracy_m FROM source").fetchone()
    conn.close()
    assert row == (0.42, 0.77)


def test_project_settings_are_the_operators_not_p2_defaults(client, tmp_path, parcels):
    """P2 stamps its own defaults writing the first layer; ours must win."""
    import sqlite3
    r = client.post("/cadastre/project", json=body(
        tmp_path, [source(parcels)], stratum_below_limit_m=-45.0,
        stratum_above_limit_m=200.0, default_plinth_offset_m=0.9))
    assert r.status_code == 200, r.text
    conn = sqlite3.connect(r.json()["db_path"])
    row = conn.execute("SELECT stratum_below_limit_m, stratum_above_limit_m, "
                       "default_plinth_offset_m FROM project_settings").fetchone()
    conn.close()
    assert row == (-45.0, 200.0, 0.9)


@pytest.mark.parametrize("field", ["horizontal_accuracy_m", "vertical_accuracy_m"])
def test_missing_accuracy_is_refused(client, tmp_path, parcels, field):
    """The contract marks both mandatory: tolerances are derived from them.

    A default here would make every source silently claim survey grade, and P4 would
    report measurement noise as encroachment.
    """
    s = source(parcels)
    del s[field]
    r = client.post("/cadastre/project", json=body(tmp_path, [s]))
    assert r.status_code == 422
    assert field in json.dumps(r.json())


@pytest.mark.parametrize("field", ["horizontal_accuracy_m", "vertical_accuracy_m"])
def test_zero_accuracy_is_refused(client, tmp_path, parcels, field):
    """Zero is not "unknown", it is a claim of perfect measurement."""
    r = client.post("/cadastre/project", json=body(tmp_path, [source(parcels, **{field: 0})]))
    assert r.status_code == 422


def test_non_zero_parapet_deduction_is_refused_at_creation(client, tmp_path, parcels):
    """`extrude` raises this at derive time - far too late to be the only check.

    By then the project exists and the data is imported. The wizard is where a person
    types the number, so the wizard is where it has to be refused.
    """
    r = client.post("/cadastre/project",
                    json=body(tmp_path, [source(parcels)], default_parapet_deduction_m=1.0))
    assert r.status_code == 422
    assert "median" in r.json()["detail"]


def test_zero_parapet_deduction_is_accepted(client, tmp_path, parcels):
    """The silence: refusing every value would be as wrong as refusing none."""
    r = client.post("/cadastre/project",
                    json=body(tmp_path, [source(parcels)], default_parapet_deduction_m=0.0))
    assert r.status_code == 200, r.text


def test_unknown_source_type_is_refused_and_names_the_known_ones(client, tmp_path, parcels):
    """A type the form offers but `project.py` ignores is a file silently dropped."""
    r = client.post("/cadastre/project",
                    json=body(tmp_path, [source(parcels, "shapefile_of_dreams")]))
    assert r.status_code == 422
    assert "parcel_map" in r.json()["detail"]


def test_a_project_with_no_sources_is_refused(client, tmp_path):
    r = client.post("/cadastre/project", json=body(tmp_path, []))
    assert r.status_code == 422


def test_rasters_alone_cannot_create_a_project(client, tmp_path, parcels):
    """A DEM is registered *against* a project. It cannot be the thing that starts one."""
    r = client.post("/cadastre/project", json=body(tmp_path, [source(parcels, "dem")]))
    assert r.status_code == 422
    assert "vector" in r.json()["detail"]


def test_a_missing_file_is_named_rather_than_half_building_a_project(client, tmp_path, parcels):
    """Every path is checked before anything is written.

    Asserting only the message would pass for the wrong reason: drop the up-front check
    and P2 fails on the same file anyway, naming it in its own error. What the guard
    actually buys is that the *parcel layer preceding it* never gets written - without
    it the project file exists, holding half the sources the operator asked for. So the
    assertion is on the absence of the file. Mutation testing is what caught this.
    """
    from pathlib import Path

    db = tmp_path / "new.gpkg"
    r = client.post("/cadastre/project", json=body(
        tmp_path, [source(parcels), source("/nope/absent.geojson", "footprint")]))
    assert r.status_code == 422
    assert "absent.geojson" in r.json()["detail"]
    assert not Path(db).exists(), "a project was half-built around a file that is not there"


def test_geometry_free_sources_are_registered_not_harmonized(client, tmp_path, parcels, tmp_path_factory):
    """A floor plan carries provenance, not a layer P2 can reproject."""
    plan = tmp_path_factory.mktemp("plans") / "block-a.pdf"
    plan.write_bytes(b"%PDF-1.4 not really a plan")
    r = client.post("/cadastre/project", json=body(
        tmp_path, [source(parcels), source(str(plan), "floorplan")]))
    assert r.status_code == 200, r.text
    got = r.json()
    assert len(got["registered_only"]) == 1
    assert got["layers"] == ["parcel"]      # the plan did not become a layer


def test_source_types_route_matches_what_the_module_handles(client):
    """Served so P1's form and this module cannot drift apart."""
    from cadastre import project
    got = client.get("/cadastre/source-types").json()
    offered = set(got["vector"]) | set(got["raster"]) | set(got["register_only"])
    assert offered == project.SOURCE_TYPES


# --- adding elevation to a project that already exists --------------------------------

def _rasters(tmp_path, db_path):
    """A DEM/DSM pair over the project's own units, in the project's own CRS.

    Written in EPSG:32643 rather than the sources' EPSG:4326 on purpose: `raster.coverage`
    divides the footprint's area by the raster's cell size, so a footprint in metres
    against a raster in degrees reports coverage near zero and every building is skipped
    as thin - a units mismatch that looks exactly like missing data.
    """
    import sqlite3

    import numpy as np
    import rasterio
    import shapely.wkb
    from rasterio.transform import from_origin

    conn = sqlite3.connect(db_path)
    geoms = [shapely.wkb.loads(r[0]) for r in conn.execute("SELECT footprint_wkb FROM unit")]
    conn.close()
    xs = [c for g in geoms for c in g.bounds[0::2]]
    ys = [c for g in geoms for c in g.bounds[1::2]]
    pad = 20.0
    x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad

    res = 0.5                                     # half-metre, as a drone survey would be
    w, h = int((x1 - x0) / res) + 1, int((y1 - y0) / res) + 1
    out = []
    for kind, value in (("dem", 100.0), ("dsm", 112.0)):
        path = tmp_path / f"{kind}.tif"
        with rasterio.open(
            path, "w", driver="GTiff", height=h, width=w, count=1, dtype="float32",
            crs="EPSG:32643", transform=from_origin(x0, y1, res, res),
        ) as dst:
            dst.write(np.full((h, w), value, "float32"), 1)
        out.append(str(path))
    return out


def test_registering_elevation_extrudes_the_project_it_was_added_to(
        client, tmp_path, parcels, buildings):
    """The flow that left a project of footprints with an empty 3D view.

    Elevation was registered, ingest reported success, and every building still had no
    height: `derive` sat behind a button on another screen with nothing pointing at it.
    Registering a DEM and a DSM over footprints has one consequence the operator wants.
    """
    import sqlite3

    db = str(tmp_path / "new.gpkg")
    r = client.post("/cadastre/project", json=body(
        tmp_path, [source(parcels), source(buildings, "footprint")]))
    assert r.status_code == 200, r.text

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM unit WHERE unit_type='building' "
                        "AND lower_limit IS NULL").fetchone()[0] == 1
    conn.close()

    dem, dsm = _rasters(tmp_path, db)
    r = client.post("/cadastre/sources", json={
        "db_path": db, "ingest": True,
        "sources": [source(dem, "dem", crs="EPSG:32643"), source(dsm, "dsm", crs="EPSG:32643")],
    })
    assert r.status_code == 200, r.text
    assert r.json()["heights_derived"] == 1, r.json()

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM unit WHERE unit_type='building' "
                        "AND lower_limit IS NULL").fetchone()[0] == 0
    conn.close()


def test_adding_a_vector_source_does_not_extrude_anything(client, tmp_path, parcels, buildings):
    """No elevation registered, so there is still nothing to measure a height from."""
    import sqlite3

    db = str(tmp_path / "new.gpkg")
    client.post("/cadastre/project", json=body(tmp_path, [source(parcels)]))
    r = client.post("/cadastre/sources", json={
        "db_path": db, "ingest": True, "sources": [source(buildings, "footprint")]})
    assert r.status_code == 200, r.text
    assert "heights_derived" not in r.json()

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM unit WHERE unit_type='building' "
                        "AND lower_limit IS NULL").fetchone()[0] == 1
    conn.close()


def test_a_project_created_with_elevation_is_extruded_at_creation(
        client, tmp_path, parcels, buildings):
    """Elevation given to the wizard counts as much as elevation added later.

    Auto-derive was wired only into `/sources`, so creating a project with all four
    files at once - parcels, footprints, DEM, DSM, which is the obvious way to do it -
    registered both rasters and extruded nothing. The 3D view then told the operator to
    add elevation they had already added.
    """
    import sqlite3

    db = str(tmp_path / "new.gpkg")
    seed = client.post("/cadastre/project", json=body(
        tmp_path, [source(parcels), source(buildings, "footprint")]))
    assert seed.status_code == 200, seed.text
    dem, dsm = _rasters(tmp_path, db)

    fresh = str(tmp_path / "withelev.gpkg")
    r = client.post("/cadastre/project", json={
        "db_path": fresh,
        "project_crs": "EPSG:32643", "vertical_datum": "EGM2008",
        "stratum_below_limit_m": -30.0, "stratum_above_limit_m": 150.0,
        "default_plinth_offset_m": 0.6, "default_parapet_deduction_m": 0.0,
        "ulpin_version": "v1", "ruleset_version": "r1",
        "sources": [source(parcels), source(buildings, "footprint"),
                    source(dem, "dem", crs="EPSG:32643"),
                    source(dsm, "dsm", crs="EPSG:32643")],
    })
    assert r.status_code == 200, r.text
    assert r.json()["heights_derived"] == 1

    conn = sqlite3.connect(fresh)
    assert conn.execute("SELECT count(*) FROM unit WHERE unit_type='building' "
                        "AND lower_limit IS NULL").fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM unit WHERE unit_type='floor'").fetchone()[0] == 0, \
        "the envelope, and no floor duplicating it"
    conn.close()


def test_creating_without_elevation_reports_no_heights(client, tmp_path, parcels):
    """Nothing to measure from, so the key is absent rather than zero."""
    r = client.post("/cadastre/project", json=body(tmp_path, [source(parcels)]))
    assert "heights_derived" not in r.json()


# --- settings are asked for, never assumed ---------------------------------------------

@pytest.mark.parametrize("field", [
    "project_crs", "vertical_datum", "stratum_below_limit_m",
    "stratum_above_limit_m", "default_plinth_offset_m",
])
def test_a_missing_project_setting_is_refused_not_defaulted(client, tmp_path, parcels, field):
    """Every one of these used to default to an Indian value.

    A caller in Kenya or Germany omitting `project_crs` had their data reprojected into
    UTM 43N and every number downstream stayed plausible: areas distorted by a factor
    growing with distance from 75E, parcels landing in the Bay of Bengal, and no rule
    able to notice - ingest stamps each unit *with* the setting rather than checking
    against it, so `crs_mismatch` compares a value to itself.
    """
    payload = body(tmp_path, [source(parcels)])
    del payload[field]
    r = client.post("/cadastre/project", json=payload)
    assert r.status_code == 422, r.text
    assert field in r.text


def test_a_route_without_a_project_path_is_refused_not_pointed_at_a_stray_file(client):
    """`sqlite3.connect` creates the file it is given.

    Eight routes defaulted `db_path` to "pilot.gpkg", so a caller who forgot it created
    an empty database beside the server process and then got a 404 or a 500 stack trace -
    never "you did not say which project".
    """
    assert client.get("/cadastre/document").status_code == 422
    assert client.get("/cadastre/runs/latest").status_code == 422
