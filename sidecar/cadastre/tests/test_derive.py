"""The seam between ingest and extrude.

Ingest imports footprints with no heights, because P2 registers rasters but does not
deliver elevation through the GeoPackage. Extrude can derive heights but does not know
where a project's rasters live. Nothing joined the two, so the chain stopped at
footprints: no heights, no floors, nothing approvable. That gap only became visible by
running the whole chain.
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from cadastre import derive, store, validate
from cadastre.models import CreatedBy, Representation, Status, Unit, UnitType
from cadastre.ulpin.encode import Stratum, format_ulpin, parse_ulpin
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

E, N = 445000.0, 1434000.0
PARENT = "KA05B012345678"
GROUND, SLAB = 912.4, 934.0
FOOTPRINT = box(E + 8, N + 6, E + 32, N + 24)
PARCEL = box(E, N, E + 40, N + 30)


@pytest.fixture
def project(tmp_path):
    """A project as ingest leaves it: footprints, no heights, rasters registered."""
    dem, dsm = tmp_path / "dem.tif", tmp_path / "dsm.tif"
    x0, y0, x1, y1 = E - 10, N - 10, E + 60, N + 50
    res = 0.5
    w, h = int((x1 - x0) / res), int((y1 - y0) / res)
    xs = x0 + (np.arange(w) + 0.5) * res
    ys = y1 - (np.arange(h) + 0.5) * res
    xx, yy = np.meshgrid(xs, ys)
    ground = np.full(xx.shape, GROUND, "float32")
    surface = ground.copy()
    mnx, mny, mxx, mxy = FOOTPRINT.bounds
    surface[(xx >= mnx) & (xx <= mxx) & (yy >= mny) & (yy <= mxy)] = SLAB
    for path, arr in ((dem, ground), (dsm, surface)):
        with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1,
                           dtype="float32", crs="EPSG:32643",
                           transform=from_origin(x0, y1, res, res), nodata=-9999.0) as dst:
            dst.write(arr, 1)

    db = tmp_path / "p.gpkg"
    conn = store.connect(str(db))
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
    conn.execute("INSERT INTO source VALUES ('SRC-1', 0.20, 0.10)")
    conn.execute("INSERT INTO raster VALUES ('R-DEM','DEM',?,'EPSG:32643','EGM2008',0.5,'SRC-1')",
                 (str(dem),))
    conn.execute("INSERT INTO raster VALUES ('R-DSM','DSM',?,'EPSG:32643','EGM2008',0.5,'SRC-1')",
                 (str(dsm),))
    conn.execute("INSERT INTO project_settings VALUES "
                 "('EPSG:32643','EGM2008',-30.0,150.0,0.6,0.0,'v1','r1')")

    def unit(uid, kind, geom, ulpin_prov=None):
        return Unit(unit_id=uid, unit_type=kind, status=Status.NEEDS_REVIEW,
                    crs="EPSG:32643", vertical_datum="EGM2008",
                    footprint_2d=mapping(geom), source_ids=["SRC-1"],
                    created_by=CreatedBy.DERIVED, representation=Representation.PRISM,
                    ulpin_provisional=ulpin_prov, ulpin_version="v1",
                    attributes={"parent_ulpin_14": PARENT}
                    if kind is UnitType.LAND_PARCEL else {})

    store.save_unit(conn, unit("PCL-1", UnitType.LAND_PARCEL, PARCEL))
    # Minted, never hand-typed: a literal string with a wrong check character is
    # correctly refused by parse_ulpin, which makes for a confusing test failure.
    store.save_unit(conn, unit("BLD-1", UnitType.BUILDING, FOOTPRINT,
                               format_ulpin(PARENT, 1, Stratum.ABOVE, 0, 0)))
    from datetime import UTC, datetime

    from cadastre.models import Relationship, RelType
    now = datetime.now(UTC)
    store.save_relationship(conn, Relationship("PCL-1", "BLD-1", RelType.CONTAINS, now))
    store.save_relationship(conn, Relationship("BLD-1", "PCL-1", RelType.INSIDE, now))
    conn.commit()
    return conn


def test_heights_and_floors_are_derived(project):
    r = derive.derive_heights(project, default_floor_count=7)
    assert r.heights_derived == 1
    assert r.floors_created == 7
    assert r.skipped_no_raster == []

    b = store.get_unit(project, "BLD-1")
    assert b.lower_limit == pytest.approx(GROUND + 0.6, abs=0.05)
    assert b.upper_limit == pytest.approx(SLAB, abs=0.05)


def test_a_parcel_column_is_anchored_to_its_own_ground(project):
    """The stratum limits are relative to ground, not absolute.

    Read absolutely, a -30/+150 column over ground at 912 m sits entirely below its own
    buildings and every structure on the parcel raises ESCAPES_PARENT -- which is exactly
    what the first end-to-end run produced.
    """
    derive.derive_heights(project, default_floor_count=7)
    p = store.get_unit(project, "PCL-1")
    assert p.lower_limit == pytest.approx(GROUND - 30, abs=0.05)
    assert p.upper_limit == pytest.approx(GROUND + 150, abs=0.05)
    assert p.attributes["stratum_is_relative_to_ground"] is True


def test_floors_inherit_the_parcel_so_they_can_be_approved(project):
    derive.derive_heights(project, default_floor_count=7)
    rows = project.execute("SELECT unit_id FROM unit WHERE unit_type='floor'").fetchall()
    assert rows
    for r in rows:
        assert store.get_unit(project, r["unit_id"]).attributes["parent_ulpin_14"]


def test_the_derived_project_validates_clean(project):
    """Extrude, then run our own rules over the result. The chain must agree with itself."""
    derive.derive_heights(project, default_floor_count=7)
    units, rels, sources, settings = store.load_project(project)
    result = validate.run(units, rels, sources, settings)
    assert result.findings == [], [
        f"{f.severity.value} {f.rule_id.value} on {f.unit_id}" for f in result.findings]


def test_a_building_no_raster_covers_is_left_alone_and_flagged(project):
    """FR-03: not derivable is reported, never invented."""
    far = box(E + 5000, N + 5000, E + 5020, N + 5020)
    store.save_unit(project, Unit(
        unit_id="BLD-FAR", unit_type=UnitType.BUILDING, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008", footprint_2d=mapping(far),
        source_ids=["SRC-1"], created_by=CreatedBy.DERIVED,
        representation=Representation.PRISM))
    project.commit()

    r = derive.derive_heights(project, default_floor_count=7)
    # Either skip bucket is honest here - outside the raster entirely, or under it but
    # too thinly covered. What matters is that no height was invented for it.
    assert "BLD-FAR" in (r.skipped_no_raster + r.skipped_thin_coverage)
    assert store.get_unit(project, "BLD-FAR").lower_limit is None

    units, rels, sources, settings = store.load_project(project)
    result = validate.run(units, rels, sources, settings)
    assert any(f.rule_id.value == "HEIGHTS_UNAVAILABLE" and f.unit_id == "BLD-FAR"
               for f in result.findings)
    assert not result.approvable("BLD-FAR")


# --- identity for derived floors -----------------------------------------------------
#
# `04-ulpin.md`: a unit in needs_review carries a provisional identifier that may be
# recomputed freely; only approval freezes one. Derived floors were the single kind that
# carried none, so the published record showed a raw uuid4 on exactly the units that are
# the vertical subdivision this project exists to identify.

def test_derived_floors_get_a_provisional_ulpin(project):
    r = derive.derive_heights(project, default_floor_count=7)
    assert r.floors_identified == r.floors_created == 7

    floors = [store.get_unit(project, row["unit_id"]) for row in project.execute(
        "SELECT unit_id FROM unit WHERE unit_type='floor'")]
    parsed = {}
    for f in floors:
        assert f.ulpin_provisional, f"{f.unit_id} published as a bare uuid"
        p = parse_ulpin(f.ulpin_provisional)          # also verifies the check character
        assert p["parent_ulpin_14"] == PARENT
        assert p["stratum"] is Stratum.ABOVE
        parsed[f.attributes["floor_index"]] = p

    # The level is the floor index, so the identifier reads as the storey it names.
    assert {i: parsed[i]["level"] for i in parsed} == {i: i for i in range(7)}
    # ...and every identifier is distinct, which is the whole point of the sequence.
    assert len({f.ulpin_provisional for f in floors}) == 7


def test_a_floor_identifier_is_allocated_once_and_survives_a_second_derive(project):
    """Determinism means recomputing yields the same answer, not renumbering.

    `derive` is repeatable - a second run sees no building lacking heights - but the
    sequence must be keyed to the unit, not to the order units were seen in, or a
    re-derive would hand a flat somebody owns a different identifier.
    """
    derive.derive_heights(project, default_floor_count=7)
    before = {row["unit_id"]: row["ulpin_provisional"] for row in project.execute(
        "SELECT unit_id, ulpin_provisional FROM unit WHERE unit_type='floor'")}
    derive.derive_heights(project, default_floor_count=7)
    after = {row["unit_id"]: row["ulpin_provisional"] for row in project.execute(
        "SELECT unit_id, ulpin_provisional FROM unit WHERE unit_type='floor'")}
    assert after == before


def test_a_floor_with_no_parent_parcel_is_left_unidentified(project):
    """The same refusal ingest makes: no parent, no identifier - never a placeholder.

    A building that carries neither a ULPIN nor a `parent_ulpin_14` has nothing to mint
    under. Its floors are still derived, still validated and still visible; what they do
    not get is an identifier claiming a parcel nobody chose.
    """
    orphan = box(E + 40, N + 6, E + 56, N + 20)
    store.save_unit(project, Unit(
        unit_id="BLD-ORPHAN", unit_type=UnitType.BUILDING, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008", footprint_2d=mapping(orphan),
        source_ids=["SRC-1"], created_by=CreatedBy.DERIVED,
        representation=Representation.PRISM))
    project.commit()

    r = derive.derive_heights(project, default_floor_count=2)
    assert r.floors_created == 4                      # two buildings, two floors each
    assert r.floors_identified == 2                   # only the one with a parent

    orphan_floors = [store.get_unit(project, row["unit_id"]) for row in project.execute(
        "SELECT unit_id FROM unit WHERE unit_type='floor'")
        if store.get_unit(project, row["unit_id"]).attributes.get("parent_ulpin_14") is None]
    assert orphan_floors
    assert all(f.ulpin_provisional is None for f in orphan_floors)


def test_a_floor_is_related_to_its_building_in_both_directions(project):
    """The pair, again, at the other producer.

    `derive` has written both since it was added, but nothing asserted it, so the same
    one-directional slip that hid in `ingest_gpkg` could have been introduced here by an
    edit and gone unnoticed until it reached a published page.
    """
    derive.derive_heights(project, default_floor_count=3)
    floors = [r["unit_id"] for r in project.execute(
        "SELECT unit_id FROM unit WHERE unit_type='floor'")]
    assert len(floors) == 3
    edges = {(r["rel_type"], r["from_unit_id"], r["to_unit_id"]) for r in project.execute(
        "SELECT rel_type, from_unit_id, to_unit_id FROM unit_relationship")}
    for uid in floors:
        assert ("contains", "BLD-1", uid) in edges
        assert ("inside", uid, "BLD-1") in edges


def test_a_storey_above_the_format_ceiling_is_left_unidentified(project):
    """The level field holds two digits, so the scheme tops out at storey 99.

    A 101-storey building is not a reason to wrap 100 round to `A00` and hand two
    different floors identifiers that differ only by sequence. The floors are still
    derived and still validated; the ones past the ceiling carry no identifier, and
    `floors_identified` says how many did.
    """
    r = derive.derive_heights(project, default_floor_count=101)
    assert r.floors_created == 101
    assert r.floors_identified == 100                 # indices 0..99

    unnamed = [store.get_unit(project, row["unit_id"]) for row in project.execute(
        "SELECT unit_id FROM unit WHERE unit_type='floor' AND ulpin_provisional IS NULL")]
    assert [u.attributes["floor_index"] for u in unnamed] == [100]
