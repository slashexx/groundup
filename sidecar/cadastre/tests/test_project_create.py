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


def body(tmp_path, sources, **over):
    b = {"db_path": str(tmp_path / "new.gpkg"), "sources": sources}
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
