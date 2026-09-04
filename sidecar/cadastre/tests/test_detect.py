"""Registered rasters -> the review queue, and the route P1 reaches it by.

Most of this runs with a **fake detector**, deliberately. P3's dependencies are not
installed in CI, and a test that skips is not a guard; what actually goes wrong at this
seam is not the model but the georeferencing handed to it, and that is assertable without
opencv, onnxruntime or a single weight. One test at the end runs the real thing when it is
available, so the wiring is exercised locally.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest
import rasterio
import shapely.geometry
from cadastre import detect, store, suggestions
from cadastre.app import app
from cadastre.models import ProjectSettings
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

SETTINGS = ProjectSettings(
    project_crs="EPSG:32643", vertical_datum="EGM2008",
    stratum_below_limit_m=-30.0, stratum_above_limit_m=150.0,
    default_plinth_offset_m=0.6, default_parapet_deduction_m=0.0,
    ulpin_version="v1", ruleset_version="r1",
)

RES = 0.5
ORIGIN_E, ORIGIN_N = 276650.0, 2110660.0
GROUND, SLAB = 912.4, 925.0


@pytest.fixture
def project(tmp_path):
    """A project with a DEM and a DSM registered, as `make_demo_rasters` leaves one."""
    n = 120
    dem = np.full((n, n), GROUND, dtype="float32")
    dsm = dem.copy()
    dsm[20:60, 20:60] = SLAB
    transform = from_origin(ORIGIN_E, ORIGIN_N, RES, RES)

    paths = {}
    for name, arr in (("dem", dem), ("dsm", dsm)):
        path = tmp_path / f"{name}.tif"
        with rasterio.open(path, "w", driver="GTiff", height=n, width=n, count=1,
                           dtype="float32", crs="EPSG:32643", transform=transform,
                           nodata=-9999.0) as dst:
            dst.write(arr, 1)
        paths[name] = str(path)

    conn = store.connect(str(tmp_path / "p.gpkg"))
    store.init_schema(conn)
    conn.executescript(
        "CREATE TABLE source (source_id TEXT PRIMARY KEY, horizontal_accuracy_m REAL,"
        " vertical_accuracy_m REAL);"
        "CREATE TABLE raster (raster_id TEXT PRIMARY KEY, kind TEXT, path TEXT,"
        " crs TEXT, vertical_datum TEXT, resolution_m REAL, source_id TEXT);"
        "CREATE TABLE project_settings (project_crs TEXT, vertical_datum TEXT,"
        " stratum_below_limit_m REAL, stratum_above_limit_m REAL,"
        " default_plinth_offset_m REAL, default_parapet_deduction_m REAL,"
        " ulpin_version TEXT, ruleset_version TEXT);")
    conn.execute("INSERT INTO source VALUES ('SRC-ELEV', 0.20, 0.10)")
    conn.execute("INSERT INTO raster VALUES ('RST-DEM','DEM',?,'EPSG:32643','EGM2008',?,'SRC-ELEV')",
                 (paths["dem"], RES))
    conn.execute("INSERT INTO raster VALUES ('RST-DSM','DSM',?,'EPSG:32643','EGM2008',?,'SRC-ELEV')",
                 (paths["dsm"], RES))
    conn.execute("INSERT INTO project_settings VALUES "
                 "('EPSG:32643','EGM2008',-30.0,150.0,0.6,0.0,'v1','r1')")
    conn.commit()
    return conn


class Spy:
    """A detector that records what it was handed and returns one usable suggestion."""

    def __init__(self, geometry=None):
        self.calls: list[dict] = []
        self.geometry = geometry or shapely.geometry.box(
            ORIGIN_E + 10, ORIGIN_N - 30, ORIGIN_E + 30, ORIGIN_N - 10)

    def __call__(self, dsm, dem, raster_ids, crs, transform):
        self.calls.append({"dsm": dsm, "dem": dem, "raster_ids": raster_ids,
                           "crs": crs, "transform": transform})
        return [{
            # A fresh id every run, as P3 does - which is exactly why re-detection
            # cannot be caught by matching ids.
            "suggestion_id": str(uuid.uuid4()),
            "kind": "building_outline",
            "geometry": shapely.geometry.mapping(self.geometry),
            "crs": crs,
            "source_raster_ids": raster_ids,
            "confidence": 0.9,
            "model": {"name": "spy", "version": "0", "run_at": "2026-09-04T12:00:00+00:00"},
            "attributes": {"floor_count": 4, "ground_level_m": GROUND, "roof_level_m": SLAB},
            "review": {"state": "pending"},
        }]


# --- the georeferencing, which is the thing that actually goes wrong -----------------

def test_the_detector_is_given_the_rasters_own_transform(project):
    """Not the identity, and not None.

    P3's `extract_from_ndsm` takes an optional transform and falls back to the identity,
    which returns polygons in pixel indices - plain floats, indistinguishable from metres
    to everything downstream. A building at (50, 50) read as UTM 43N sits about 276 km
    from its parcel, in the sea, and every check runs happily on it. Handing the transform
    over is this module's whole reason to exist, so it is asserted rather than assumed.
    """
    spy = Spy()
    detect.run(project, SETTINGS, detector=spy)

    (call,) = spy.calls
    assert call["transform"] is not None
    assert call["transform"] != rasterio.Affine.identity()
    assert call["transform"].c == pytest.approx(ORIGIN_E)     # easting of the top-left
    assert call["transform"].f == pytest.approx(ORIGIN_N)     # northing of the top-left
    assert call["transform"].a == pytest.approx(RES)


def test_the_detector_reads_the_registered_surfaces_and_is_told_which(project):
    spy = Spy()
    report = detect.run(project, SETTINGS, detector=spy)

    (call,) = spy.calls
    assert call["dem"].max() == pytest.approx(GROUND)         # the DEM, flat
    assert call["dsm"].max() == pytest.approx(SLAB)           # the DSM, with the roof
    assert call["raster_ids"] == ["RST-DSM", "RST-DEM"]
    assert call["crs"] == "EPSG:32643"
    assert (report.dsm_raster_id, report.dem_raster_id) == ("RST-DSM", "RST-DEM")


# --- what happens to what it finds ---------------------------------------------------

def test_what_is_found_lands_in_the_queue_and_nowhere_else(project):
    """Detection fills the queue. It does not create units - that needs a person."""
    report = detect.run(project, SETTINGS, detector=Spy())

    assert (report.found, report.stored) == (1, 1)
    assert len(suggestions.listing(project, "pending")) == 1
    assert project.execute("SELECT count(*) FROM unit").fetchone()[0] == 0


def test_a_suggestion_the_contract_refuses_never_reaches_the_queue(project):
    """The detector is upstream code like any other, and passes the same gate.

    A polygon in the wrong frame is exactly what this seam is guarding against, so the
    guard has to apply to output from the detector too, not only to a posted batch.
    """
    class Wrong(Spy):
        def __call__(self, dsm, dem, raster_ids, crs, transform):
            out = super().__call__(dsm, dem, raster_ids, crs, transform)
            out[0]["crs"] = "EPSG:4326"
            return out

    with pytest.raises(suggestions.ContractViolation, match="EPSG:4326"):
        detect.run(project, SETTINGS, detector=Wrong())
    assert project.execute("SELECT count(*) FROM ai_suggestion").fetchone()[0] == 0


def test_a_decision_already_made_survives_a_second_detection(project):
    """Pressing Analyse again must not re-ask a settled question.

    P3 mints a fresh `suggestion_id` every run, so the id guard in `receive` sees two
    unrelated suggestions and the rejected outline comes straight back to the queue with
    a new name. Only the geometry gives it away.
    """
    detect.run(project, SETTINGS, detector=Spy())
    sid = suggestions.listing(project)[0]["suggestion_id"]
    suggestions.review(project, sid, "rejected", "bibisha")

    report = detect.run(project, SETTINGS, detector=Spy())
    assert report.found == 1 and report.stored == 0
    assert report.rediscovered == [sid]
    assert suggestions.listing(project, "pending") == []


def test_pressing_analyse_twice_does_not_stack_the_same_building(project):
    detect.run(project, SETTINGS, detector=Spy())
    report = detect.run(project, SETTINGS, detector=Spy())

    assert report.rediscovered == [suggestions.listing(project)[0]["suggestion_id"]]
    assert len(suggestions.listing(project)) == 1


def test_a_building_somewhere_else_is_still_queued(project):
    """The silence. A rule that swallowed every second detection would make the button
    work once and then quietly do nothing."""
    detect.run(project, SETTINGS, detector=Spy())
    far = shapely.geometry.box(ORIGIN_E + 500, ORIGIN_N - 530,
                               ORIGIN_E + 520, ORIGIN_N - 510)
    report = detect.run(project, SETTINGS, detector=Spy(geometry=far))

    assert report.rediscovered == [] and report.stored == 1
    assert len(suggestions.listing(project, "pending")) == 2


def test_a_barely_overlapping_detection_is_a_different_building(project):
    """The threshold is symmetric and it is `ingest_gpkg.MAJORITY`: more than half of
    *each* footprint, so a neighbour clipping a corner is not swallowed."""
    detect.run(project, SETTINGS, detector=Spy())
    # 20 x 20 m box shifted 15 m east: 25% of each, under the majority either way.
    corner = shapely.geometry.box(ORIGIN_E + 25, ORIGIN_N - 45, ORIGIN_E + 45,
                                  ORIGIN_N - 25)
    report = detect.run(project, SETTINGS, detector=Spy(geometry=corner))

    assert report.rediscovered == [] and report.stored == 1


# --- nothing to look at is an answer, not an error -----------------------------------

def test_a_project_with_no_rasters_reports_it_rather_than_failing(project):
    """The same answer `derive` gives, for the same reason: P2 registers rasters but does
    not always deliver them, and an empty registry is a real condition."""
    project.execute("DELETE FROM raster")
    project.commit()
    spy = Spy()
    report = detect.run(project, SETTINGS, detector=spy)

    assert (report.found, report.stored, report.dsm_raster_id) == (0, 0, None)
    assert spy.calls == [], "the detector was called with no surfaces to read"


# --- the route P1 uses ---------------------------------------------------------------

def test_the_detect_route_says_which_install_is_missing(project, tmp_path, monkeypatch):
    """P3's dependencies are declared but nothing installs them, so the failure has to
    name the fix.

    503 and not 500: the request is well formed and the code is correct, this deployment
    simply cannot answer it. Exercised against a *complete* project, so a 422 from an
    unbuilt one cannot stand in for the answer under test.
    """
    monkeypatch.setattr(detect, "p3_detector", _raises_unavailable)
    project.commit()

    r = TestClient(app).post("/cadastre/detect", json={"db_path": str(tmp_path / "p.gpkg")})
    assert r.status_code == 503, r.text
    assert "opencv" in r.json()["detail"] and "onnxruntime" in r.json()["detail"]


def test_the_detect_route_queues_what_it_finds(tmp_path, project, monkeypatch):
    """The call P1's AI screen makes, and the queue it opens afterwards."""
    monkeypatch.setattr(detect, "p3_detector", lambda: Spy())
    project.commit()
    db = str(tmp_path / "p.gpkg")

    r = TestClient(app).post("/cadastre/detect", json={"db_path": db})
    assert r.status_code == 200, r.text
    assert r.json()["stored"] == 1

    queue = TestClient(app).get("/cadastre/suggestions",
                                params={"db_path": db, "state": "pending"}).json()
    assert queue["count"] == 1
    assert queue["suggestions"][0]["review"]["state"] == "pending"
    # ...and still nothing in the register.
    units = TestClient(app).get("/cadastre/document", params={"db_path": db}).json()["units"]
    assert units == []


def _raises_unavailable():
    raise detect.AIUnavailable(
        f"the AI block is not installed here (cv2 is missing).\n  {detect.P3_INSTALL}")


# --- and the real detector, where it is installed ------------------------------------

def test_the_real_p3_finds_the_building_in_the_surface(project):
    """The wiring, end to end, with no fake anywhere.

    Skipped where P3's dependencies are absent - which is CI, and is why every assertion
    above is written to hold without them.
    """
    pytest.importorskip("cv2", reason="P3 not installed; see blocks/p3-ai.md")
    report = detect.run(project, SETTINGS)

    assert report.found == 1
    found = suggestions.listing(project, "pending")[0]
    ring = shapely.geometry.shape(found["geometry"])
    assert ring.bounds[0] > 276_000, "geometry is in pixel indices, not project metres"
    assert found["attributes"]["floor_count"] == 4
    assert found["attributes"]["roof_level_m"] == pytest.approx(SLAB, abs=0.1)
