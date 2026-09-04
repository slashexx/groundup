"""Importing P2's GeoPackage.

Geometry here is axis-aligned and metric so every expected value is arithmetic rather
than approximate: a 10x10 m footprint inside a 100x100 m parcel is 100 m2 of 10000 m2,
and a footprint split down the middle is exactly 0.5 - the threshold's boundary case.
"""

from __future__ import annotations

import struct

import pytest
import shapely.geometry
from cadastre import ingest_gpkg, store
from cadastre.models import ProjectSettings, RelType, Status, UnitType

SETTINGS = ProjectSettings(
    project_crs="EPSG:32643", vertical_datum="EGM2008",
    stratum_below_limit_m=-30.0, stratum_above_limit_m=150.0,
    default_plinth_offset_m=0.6, default_parapet_deduction_m=0.0,
    ulpin_version="v1", ruleset_version="r1",
)

PARENT = "KA05B012345678"


def gpkg_blob(geom, srs_id: int = 32643, envelope: bool = True) -> bytes:
    """Encode a shapely geometry the way OGR writes it into a GeoPackage.

    Written out rather than mocked because the header is precisely what the import has
    to cope with; a test that fed plain WKB would pass while the real file failed.
    """
    flags = 0x01 | (0x02 if envelope else 0x00)     # little-endian, envelope indicator 1
    header = b"GP" + bytes([0, flags]) + struct.pack("<i", srs_id)
    if envelope:
        minx, miny, maxx, maxy = geom.bounds
        header += struct.pack("<4d", minx, maxx, miny, maxy)
    return header + geom.wkb


def rect(x0, y0, x1, y1):
    return shapely.geometry.box(x0, y0, x1, y1)


@pytest.fixture
def gpkg(tmp_path):
    """A GeoPackage shaped the way P2 leaves one, with our tables applied on top."""
    conn = store.connect(str(tmp_path / "p2.gpkg"))
    store.init_schema(conn)
    conn.executescript(
        "CREATE TABLE parcel (parcel_local_id TEXT, parent_ulpin_14 TEXT,"
        " source_id TEXT, geom BLOB);"
        "CREATE TABLE building_footprint (building_local_id TEXT, parcel_local_id TEXT,"
        " floors_count INTEGER, source_id TEXT, geom BLOB);"
        "CREATE TABLE source (source_id TEXT PRIMARY KEY, horizontal_accuracy_m REAL,"
        " vertical_accuracy_m REAL);"
    )
    conn.execute("INSERT INTO source VALUES ('SRC-1', 0.20, 0.25)")
    conn.commit()
    return conn


def add_parcel(conn, local, geom, parent=PARENT):
    conn.execute("INSERT INTO parcel VALUES (?,?,?,?)",
                 (local, parent, "SRC-1", gpkg_blob(geom)))
    conn.commit()


def add_building(conn, local, geom, parcel=None, floors=None):
    conn.execute("INSERT INTO building_footprint VALUES (?,?,?,?,?)",
                 (local, parcel, floors, "SRC-1", gpkg_blob(geom)))
    conn.commit()


# --- the GeoPackage geometry header -------------------------------------------------

def test_a_gpkg_blob_is_not_plain_wkb():
    """The guard's premise. If this ever stops holding, the strip is dead code."""
    import shapely.wkb
    from shapely.errors import GEOSException
    blob = gpkg_blob(rect(0, 0, 10, 10))
    with pytest.raises(GEOSException):
        shapely.wkb.loads(blob)
    assert ingest_gpkg.gpkg_geometry(blob).area == 100.0


def test_the_envelope_length_is_read_from_the_flags_not_assumed():
    """OGR omits the envelope for some geometries; a fixed offset silently breaks."""
    with_env = ingest_gpkg.gpkg_geometry(gpkg_blob(rect(0, 0, 10, 10), envelope=True))
    without = ingest_gpkg.gpkg_geometry(gpkg_blob(rect(0, 0, 10, 10), envelope=False))
    assert with_env.area == without.area == 100.0


def test_plain_wkb_still_decodes():
    """Our own footprint_wkb column has no GeoPackage header."""
    assert ingest_gpkg.gpkg_geometry(rect(0, 0, 4, 5).wkb).area == 20.0


# --- refusing to guess ---------------------------------------------------------------

def test_a_parcel_without_a_parent_ulpin_gets_no_provisional_identifier(gpkg):
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100), parent=None)
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    parcel = report.units[0]
    assert parcel.ulpin_provisional is None
    assert parcel.ulpin is None
    assert report.minted == 0


def test_a_parcel_with_a_parent_ulpin_is_minted_under_it(gpkg):
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    from cadastre.ulpin import encode
    provisional = report.units[0].ulpin_provisional
    # Surface stratum, level 00, first sequence on that level - and a valid check char.
    assert provisional.startswith(f"{PARENT}-V1-S00-000-")
    assert encode.verify(provisional)
    assert report.minted == 1


def test_imported_buildings_have_no_height(gpkg):
    """FR-03. No DEM/DSM arrives through the GeoPackage, so the range is unknown."""
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_building(gpkg, "B-1", rect(10, 10, 20, 20), parcel="P-1", floors=4)
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    b = next(u for u in report.units if u.unit_type is UnitType.BUILDING)
    assert b.lower_limit is None and b.upper_limit is None
    assert b.attributes["heights_unavailable"]
    # The floor count is recorded as evidence; it is not acted on without a height.
    assert b.attributes["floor_count"] == 4


def test_a_parcel_keeps_the_project_stratum_as_its_column(gpkg):
    """Settings, not measurements - so recording them is not a guess about the ground."""
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    parcel = ingest_gpkg.import_project(gpkg, SETTINGS).units[0]
    assert (parcel.lower_limit, parcel.upper_limit) == (-30.0, 150.0)


# --- resolving a building to its parcel ----------------------------------------------

def test_a_majority_share_attaches_the_building(gpkg):
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_parcel(gpkg, "P-2", rect(100, 0, 200, 100))
    add_building(gpkg, "B-1", rect(90, 10, 110, 30))     # 10x20 in P-1, 10x20 in P-2...
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    # ...which is exactly 0.5 each: no majority, so neither parcel claims it.
    assert report.unresolved == ["B-1"]
    assert report.relationships == []


def test_a_footprint_straddling_a_boundary_still_attaches_to_its_own_parcel(gpkg):
    """The reason the threshold is a share and not `intersects`.

    A metre of slop along a shared boundary is normal between two sources. Requiring a
    majority keeps the building with the parcel that actually holds it instead of
    reporting an ambiguity a reviewer would have to dismiss on every single building.
    """
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_parcel(gpkg, "P-2", rect(100, 0, 200, 100))
    add_building(gpkg, "B-1", rect(89, 10, 100.5, 30))   # 0.5 m over the boundary
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    assert report.unresolved == []
    b = next(u for u in report.units if u.unit_type is UnitType.BUILDING)
    assert b.attributes["parcel_share"] > 0.95
    assert len(report.relationships) == 2          # contains + inside, one attachment


def test_a_parcel_and_its_building_are_related_in_both_directions(gpkg):
    """Containment is stored as a pair, and both halves are load-bearing.

    `contains` is what validation walks; `inside` is what a consumer reads to find a
    unit's parent, and P5's adapter builds lineage from that edge *alone*. Ingest wrote
    only `contains`, so every live-published building had no parcel above it - the record
    opened on a building floating free, which is the wrong way round for a land record.
    The fixture and `derive` have always stored both; ingest was the one that did not,
    and the gap was invisible until P6 published live data.
    """
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_building(gpkg, "B-1", rect(10, 10, 20, 20))
    report = ingest_gpkg.import_project(gpkg, SETTINGS)

    parcel = next(u for u in report.units if u.unit_type is UnitType.LAND_PARCEL)
    building = next(u for u in report.units if u.unit_type is UnitType.BUILDING)
    assert {(r.rel_type, r.from_unit_id, r.to_unit_id) for r in report.relationships} == {
        (RelType.CONTAINS, parcel.unit_id, building.unit_id),
        (RelType.INSIDE, building.unit_id, parcel.unit_id),
    }

    # And both are persisted: `unit_relationship` is keyed on (from, to, rel_type), so
    # the pair is two rows rather than one silently replacing the other.
    rows = gpkg.execute(
        "SELECT rel_type FROM unit_relationship ORDER BY rel_type").fetchall()
    assert [r[0] for r in rows] == ["contains", "inside"]


def test_an_explicit_parcel_id_wins_over_geometry(gpkg):
    """P2 knows something we do not; a named parcel is authoritative."""
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_parcel(gpkg, "P-2", rect(100, 0, 200, 100))
    add_building(gpkg, "B-1", rect(110, 10, 120, 20), parcel="P-1")   # sits in P-2
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    parcel_uid = next(u for u in report.units
                      if u.attributes.get("local_id") == "P-1").unit_id
    assert report.relationships[0].from_unit_id == parcel_uid


def test_a_named_parcel_that_is_absent_is_reported_not_replaced(gpkg):
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_building(gpkg, "B-1", rect(10, 10, 20, 20), parcel="P-NOPE")
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    b = next(u for u in report.units if u.unit_type is UnitType.BUILDING)
    assert "P-NOPE" in b.attributes["parcel_unresolved"]
    assert report.unresolved == ["B-1"]


def test_a_building_over_no_parcel_at_all_is_unresolved(gpkg):
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_building(gpkg, "B-1", rect(500, 500, 510, 510))
    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    assert report.unresolved == ["B-1"]


# --- repeatability -------------------------------------------------------------------

def test_importing_twice_does_not_mint_a_second_identity(gpkg):
    """`unit_id` is allocated once. A re-import after P2 adds a layer is routine."""
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_building(gpkg, "B-1", rect(10, 10, 20, 20), parcel="P-1")
    first = ingest_gpkg.import_project(gpkg, SETTINGS)
    ids = sorted(u.unit_id for u in first.units)

    second = ingest_gpkg.import_project(gpkg, SETTINGS)
    assert sorted(u.unit_id for u in second.units) == ids
    assert second.reused == 2 and second.created == 0
    assert gpkg.execute("SELECT COUNT(*) FROM unit").fetchone()[0] == 2


# --- utility corridors ---------------------------------------------------------------

def test_a_utility_line_becomes_a_buffered_easement(gpkg):
    gpkg.executescript(
        "CREATE TABLE utility_line (utility_local_id TEXT, utility_kind TEXT,"
        " stratum TEXT, depth_top_m REAL, depth_bottom_m REAL, corridor_width_m REAL,"
        " source_id TEXT, geom BLOB);")
    line = shapely.geometry.LineString([(0, 50), (100, 50)])
    gpkg.execute("INSERT INTO utility_line VALUES (?,?,?,?,?,?,?,?)",
                 ("U-1", "water", "below", -1.5, -2.5, 4.0, "SRC-1", gpkg_blob(line)))
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    gpkg.commit()

    report = ingest_gpkg.import_project(gpkg, SETTINGS)
    u = next(x for x in report.units if x.unit_type is UnitType.UNDERGROUND_FEATURE)
    # 100 m of line buffered by half of a 4 m corridor, flat caps: exactly 400 m2.
    assert shapely.geometry.shape(u.footprint_2d).area == pytest.approx(400.0, abs=1e-6)
    assert u.attributes["easement"] is True
    # Depths are relative to ground and no DEM has arrived, so they are not converted.
    assert u.lower_limit is None and u.upper_limit is None
    assert u.attributes["depth_top_m"] == -1.5


# --- the refusals --------------------------------------------------------------------

def test_a_geopackage_with_no_parcel_layer_is_refused(gpkg):
    gpkg.execute("DROP TABLE parcel")
    with pytest.raises(ingest_gpkg.LayerMissing):
        ingest_gpkg.import_project(gpkg, SETTINGS)


def test_imported_units_are_never_born_approved(gpkg):
    add_parcel(gpkg, "P-1", rect(0, 0, 100, 100))
    add_building(gpkg, "B-1", rect(10, 10, 20, 20), parcel="P-1")
    for u in ingest_gpkg.import_project(gpkg, SETTINGS).units:
        assert u.status is Status.NEEDS_REVIEW
        assert u.ulpin is None
