"""Detection must not re-offer buildings the project already holds.

Found on the Trivandrum pilot: 910 buildings imported from footprints, then detect
returned 727 suggestions of which **every single one** overlapped an existing building.
`rediscovered` was empty, because that check compares a detection only against other
suggestions - it stops pressing the button twice from stacking outlines, which is what it
was written for, but it cannot see the register.

A review queue of 727 items that are all already mapped is worse than an empty one. It is
the failure this project keeps guarding against in other forms: findings a reviewer learns
to click past.
"""

from __future__ import annotations

import pytest
import shapely.geometry
from cadastre import detect, store
from cadastre.models import CreatedBy, Representation, Status, Unit, UnitType

E, N = 445000.0, 1434000.0


def _square(x0, y0, size):
    return {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]]]}


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    store.init_schema(c)
    # P2 owns the raster registry; a cadastre-only schema does not create it.
    c.executescript(
        "CREATE TABLE IF NOT EXISTS raster (raster_id TEXT PRIMARY KEY, kind TEXT,"
        " path TEXT, crs TEXT, vertical_datum TEXT, resolution_m REAL, source_id TEXT);")
    return c


def _building(conn, uid, x0, y0, size=20.0):
    store.save_unit(conn, Unit(
        unit_id=uid, unit_type=UnitType.BUILDING, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008", footprint_2d=_square(x0, y0, size),
        source_ids=["SRC-1"], created_by=CreatedBy.DERIVED,
        representation=Representation.PRISM))
    conn.commit()


def test_a_detection_of_a_mapped_building_is_recognised(conn):
    _building(conn, "BLD-1", E, N)
    same = shapely.geometry.shape(_square(E + 1, N + 1, 20.0))     # same ground, jittered
    assert detect.already_mapped(conn, same) == "BLD-1"


def test_a_genuinely_new_building_is_not(conn):
    _building(conn, "BLD-1", E, N)
    elsewhere = shapely.geometry.shape(_square(E + 500, N + 500, 20.0))
    assert detect.already_mapped(conn, elsewhere) is None


def test_a_neighbour_is_not_swallowed(conn):
    """Symmetric majority, so a large detection cannot absorb the small building beside
    it - the same reasoning the suggestion-level check already uses."""
    _building(conn, "BLD-BIG", E, N, size=60.0)
    small = shapely.geometry.shape(_square(E + 62, N, 8.0))
    assert detect.already_mapped(conn, small) is None


def test_a_detection_sitting_inside_a_larger_building_is_not_a_match(conn):
    _building(conn, "BLD-BIG", E, N, size=60.0)
    sliver = shapely.geometry.shape(_square(E + 10, N + 10, 6.0))   # wholly inside
    assert detect.already_mapped(conn, sliver) is None, (
        "wholly inside is not the same footprint - the containing building is much larger")


def test_detect_does_not_queue_buildings_the_project_already_holds(conn, tmp_path):
    """The whole point, end to end: a detector that re-finds every mapped building
    produces an empty queue and says why, rather than 727 items to click past.

    Real rasters rather than a monkeypatched reader - `run` opens the files itself, and
    stubbing that out would test the wiring around the bug instead of the bug.
    """
    import numpy as np
    import rasterio
    from cadastre.loader import settings_from_dict
    from rasterio.transform import from_origin

    for i in range(5):
        _building(conn, f"BLD-{i}", E + i * 100, N)

    arr = np.full((80, 200), 912.4, "float32")
    for name, kind in (("dem.tif", "DEM"), ("dsm.tif", "DSM")):
        path = tmp_path / name
        with rasterio.open(path, "w", driver="GTiff", height=80, width=200, count=1,
                           dtype="float32", crs="EPSG:32643",
                           transform=from_origin(E - 10, N + 40, 0.5, 0.5)) as dst:
            dst.write(arr, 1)
        conn.execute(
            "INSERT INTO raster (raster_id, kind, path, crs, vertical_datum, "
            "resolution_m, source_id) VALUES (?,?,?,?,?,?,?)",
            (f"R-{kind}", kind, str(path), "EPSG:32643", "EGM2008", 0.5, "SRC-1"))
    conn.commit()

    settings = settings_from_dict({
        "project_crs": "EPSG:32643", "vertical_datum": "EGM2008",
        "stratum_below_limit_m": -30.0, "stratum_above_limit_m": 150.0,
        "default_plinth_offset_m": 0.6, "default_parapet_deduction_m": 0.0,
        "ulpin_version": "v1", "ruleset_version": "r1"})

    # A detector that re-finds all five, jittered a metre, as a real one does.
    def redetects_everything(dsm, dem, raster_ids, crs, transform):
        return [{"geometry": _square(E + i * 100 + 1, N + 1, 20.0), "confidence": 0.9,
                 "attributes": {"floor_count": 3, "floor_count_method": "ndsm_division"}}
                for i in range(5)]

    report = detect.run(conn, settings, detector=redetects_everything)
    assert report.found == 5
    assert report.stored == 0, "already-mapped buildings must not enter the queue"
    assert len(report.already_mapped) == 5
