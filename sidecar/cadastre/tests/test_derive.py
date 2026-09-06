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


# --- deriving twice is not deriving twice as much -------------------------------------

def test_re_deriving_a_building_updates_its_floors_rather_than_adding_a_second_stack(project):
    """The floor stack is replaced in place, not appended to.

    `test_a_floor_identifier_is_allocated_once_and_survives_a_second_derive` above never
    exercised this: the second run finds no building with a NULL height and does nothing
    at all, so it asserts that a no-op changes nothing. The path that matters is a
    building whose heights are gone and are derived again - which is what happened in
    practice when registering a DEM re-ingested the footprint layer and nulled them.
    Floors took a fresh uuid4 per call, so the project went from 5,003 floors to 10,006
    while the report said `floors_created: 5003` both times.
    """
    derive.derive_heights(project, default_floor_count=7)
    first = {row["unit_id"] for row in project.execute(
        "SELECT unit_id FROM unit WHERE unit_type='floor'")}
    assert len(first) == 7

    # Exactly what a re-ingest does to a building: the source has no elevation in it.
    project.execute("UPDATE unit SET lower_limit=NULL, upper_limit=NULL "
                    "WHERE unit_type='building'")
    project.commit()

    report = derive.derive_heights(project, default_floor_count=7)
    assert report.floors_created == 7

    second = {row["unit_id"] for row in project.execute(
        "SELECT unit_id FROM unit WHERE unit_type='floor'")}
    assert second == first, "the same seven floors, not seven more"


def test_two_buildings_do_not_share_floor_ids(project):
    """Determinism must not collapse two buildings' ground floors into one unit."""
    from cadastre.extrude import floors as flr

    derive.derive_heights(project, default_floor_count=3)
    a = store.get_unit(project, "BLD-1")
    b = store.get_unit(project, "BLD-1")
    b.unit_id = "a-different-building"
    _units, _rels, _sources, settings = store.load_project(project)
    assert not ({f.unit_id for f in flr.split(a, 3, settings)}
                & {f.unit_id for f in flr.split(b, 3, settings)})


# --- the app should not need to be told twice ----------------------------------------

def test_registering_elevation_extrudes_the_buildings_without_a_second_call(project):
    """Adding a DEM and a DSM has one consequence the operator wants. Do it.

    Registering elevation through the Upload Data screen reported success and left the
    3D view empty, with nothing saying a step remained: `derive` lived behind a separate
    button on another screen. The elevation is the measurement; extruding from it is not
    a judgement call.
    """
    from cadastre.api import _derive_after_elevation

    assert project.execute(
        "SELECT count(*) FROM unit WHERE unit_type='building' AND lower_limit IS NULL"
    ).fetchone()[0] == 1

    result = _derive_after_elevation(project)
    assert result["heights_derived"] == 1

    b = store.get_unit(project, "BLD-1")
    assert b.lower_limit is not None and b.upper_limit is not None


def test_registering_elevation_creates_no_floor_units_at_all(project):
    """The envelope is measured; its interior is not, and must not be stated.

    This test was written once, failed, and I changed it to match the code - citing a
    docstring calling a whole-envelope floor "the honest representation of we measured
    the envelope but were not told how it is divided". The validator disagreed and the
    validator was right: that floor has the same footprint and the same height range as
    its building, so `GEOM_DUPLICATE` fires on every pair. A live project of 910 buildings
    got 910 duplicate errors the moment elevation was registered, and every unit in it
    became unapprovable.
    """
    from cadastre.api import _derive_after_elevation

    result = _derive_after_elevation(project)
    assert result["heights_derived"] == 1
    assert project.execute(
        "SELECT count(*) FROM unit WHERE unit_type='floor'").fetchone()[0] == 0

    b = store.get_unit(project, "BLD-1")
    assert b.lower_limit is not None, "the height is the whole point of the run"


def test_a_single_storey_buildings_own_floor_is_not_a_duplicate(project):
    """It coincides with its building because the building *is* one storey.

    I first justified `floors=False` above by saying this pair is a duplicate. It is not:
    the rule was flagging every single-storey building in a project, which over rural
    India is most of them. The real reason auto-derive creates no floors is that
    registering elevation measures the envelope and says nothing about the interior -
    for a one-storey building the subdivision happens to be right, for a seven-storey one
    it is wrong, and the automatic path cannot tell which it has.
    """
    derive.derive_heights(project, default_floor_count=1)
    units, rels, sources, settings = store.load_project(project)
    result = validate.run(units, rels, sources, settings)
    assert not [f for f in result.findings if f.rule_id.value == "GEOM_DUPLICATE"]


def test_two_unrelated_units_with_the_same_extent_are_still_a_duplicate(project):
    """The exemption is only the containment pair; a record entered twice still collides."""
    derive.derive_heights(project, default_floor_count=1)
    original = store.get_unit(project, "BLD-1")
    twin = store.get_unit(project, "BLD-1")
    twin.unit_id = "BLD-1-COPY"
    twin.ulpin_provisional = None
    store.save_unit(project, twin)
    project.commit()

    units, rels, sources, settings = store.load_project(project)
    result = validate.run(units, rels, sources, settings)
    assert [f for f in result.findings if f.rule_id.value == "GEOM_DUPLICATE"], \
        "two buildings with one footprint and one height range is a real duplicate"


def test_a_dem_with_no_dsm_extrudes_nothing(project):
    """One surface is not a height range, and half a pair must not half-derive."""
    from cadastre.api import _derive_after_elevation

    project.execute("DELETE FROM raster WHERE kind = 'DSM'")
    project.commit()
    assert _derive_after_elevation(project) == {}
    assert store.get_unit(project, "BLD-1").lower_limit is None


def test_re_registering_elevation_is_not_a_second_derive(project):
    """Every building already has a height, so there is nothing pending to extrude."""
    from cadastre.api import _derive_after_elevation

    _derive_after_elevation(project)
    assert _derive_after_elevation(project) == {}


# --- floor segmentation after elevation has already extruded ---------------------------

def test_floor_segmentation_still_runs_on_an_already_extruded_building(project):
    """The regression that made Floor Segmentation a permanent no-op.

    Registering elevation extrudes on its own now, so every building has a height by the
    time anyone presses Floor Segmentation - and `derive` selected only buildings with a
    NULL height. The button reported `buildings seen: 0` and a project could never get
    past one whole-envelope floor per building.
    """
    first = derive.derive_heights(project, default_floor_count=1)
    assert first.heights_derived == 1
    assert first.floors_created == 1, "the envelope itself, undivided"

    second = derive.derive_heights(project, estimate_floors=True)
    assert second.buildings_seen == 1, "the extruded building is still this run's work"
    assert second.heights_derived == 0, "it already had a height; nothing new was measured"
    assert second.floors_created > 1

    b = store.get_unit(project, "BLD-1")
    assert b.attributes["floor_count_method"] == "ndsm_division"
    assert b.confidence_score == pytest.approx(0.4)


def test_a_shorter_re_estimate_drops_the_levels_that_no_longer_exist(project):
    """Eight storeys re-estimated as seven must not leave the eighth behind.

    Floor ids are derived from the building and the index, so a re-split silently keeps
    every level the new count does not reach: still a unit, still related to the building,
    still carrying its identifier - a storey that exists in the register and nowhere else.
    """
    derive.derive_heights(project, default_floor_count=8)
    assert project.execute(
        "SELECT count(*) FROM unit WHERE unit_type='floor'").fetchone()[0] == 8

    # Clear the count so the estimator revisits it. A 21 m envelope over an assumed 3 m
    # storey estimates seven, which is one fewer than the stack already there.
    b = store.get_unit(project, "BLD-1")
    b.attributes = {k: v for k, v in b.attributes.items() if k != "floor_count"}
    store.save_unit(project, b)
    project.commit()

    report = derive.derive_heights(project, estimate_floors=True)
    assert report.floors_removed == 1
    assert project.execute(
        "SELECT count(*) FROM unit WHERE unit_type='floor'").fetchone()[0] == 7
    # Nothing is left pointing at a level that no longer exists.
    assert project.execute(
        "SELECT count(*) FROM unit_relationship r LEFT JOIN unit u "
        "ON u.unit_id = r.to_unit_id WHERE u.unit_id IS NULL").fetchone()[0] == 0


def test_an_approved_floor_is_never_dropped_by_a_re_estimate(project):
    """Its identifier is frozen and somebody is relying on it.

    Retiring a property record because a later estimate came out shorter is the opposite
    of what a register is for.
    """
    derive.derive_heights(project, default_floor_count=8)
    top = max(
        (store.get_unit(project, r["unit_id"]) for r in project.execute(
            "SELECT unit_id FROM unit WHERE unit_type='floor'")),
        key=lambda f: f.attributes["floor_index"])
    assert top.attributes["floor_index"] == 7, "the level a seven-storey re-split loses"
    # The schema refuses an approved unit with no ULPIN, which is the whole point of
    # approval: it is the transition that freezes one.
    top.ulpin = top.ulpin_provisional
    top.status = Status.APPROVED
    store.save_unit(project, top)

    b = store.get_unit(project, "BLD-1")
    b.attributes = {k: v for k, v in b.attributes.items() if k != "floor_count"}
    store.save_unit(project, b)
    project.commit()

    report = derive.derive_heights(project, estimate_floors=True)
    assert report.floors_removed == 0
    assert store.get_unit(project, top.unit_id) is not None


def test_a_declared_storey_count_is_not_replaced_by_a_guess(project):
    """A source that stated four floors knows more than an assumed storey height does."""
    b = store.get_unit(project, "BLD-1")
    b.attributes = b.attributes | {"floor_count": 4}
    store.save_unit(project, b)
    project.commit()

    derive.derive_heights(project, estimate_floors=True)
    after = store.get_unit(project, "BLD-1")
    assert after.attributes["floor_count"] == 4
    assert "floor_count_method" not in after.attributes


def test_a_building_that_declares_its_storeys_still_gets_a_floor_stack(project):
    """The condition for "needs a stack" is having no floors, not having no floor count.

    Those coincide only when nothing declares one. A source that states `floors_count`
    gives its buildings a count at ingest, so keying the selection off the count skipped
    every declared building - 28 of 51 on the first dataset that declared any - while the
    run reported success on the other 23. Silent, and only visible as buildings with no
    floors under them.
    """
    b = store.get_unit(project, "BLD-1")
    b.attributes = b.attributes | {"floor_count": 4}
    store.save_unit(project, b)
    project.commit()

    report = derive.derive_heights(project, estimate_floors=True)
    assert report.buildings_seen == 1, "declared or not, it has no floors yet"
    assert report.floors_created == 4, "the count it declared, not a guess"

    after = store.get_unit(project, "BLD-1")
    assert "floor_count_method" not in after.attributes


def test_running_floor_segmentation_twice_does_not_churn_an_estimated_stack(project):
    """Pressing the button again is cheap: an estimated stack is already this run's work."""
    first = derive.derive_heights(project, estimate_floors=True)
    assert first.floors_created > 1

    second = derive.derive_heights(project, estimate_floors=True)
    assert second.buildings_seen == 0
    assert second.floors_created == 0


def test_height_estimation_gives_a_stack_to_a_building_that_already_has_a_count(project):
    """Without asking for an estimate: the building has a count and no floors.

    This is the path where "has no stack" is the only thing that can select it. The test
    above passes even with the old count-based predicate, because asking for an estimate
    adds a second clause that happens to catch the same building - so it never isolated
    the bug it was written for.
    """
    from cadastre.api import _derive_after_elevation

    b = store.get_unit(project, "BLD-1")
    b.attributes = b.attributes | {"floor_count": 4}
    store.save_unit(project, b)
    project.commit()

    _derive_after_elevation(project)          # heights, no floors
    assert project.execute(
        "SELECT count(*) FROM unit WHERE unit_type='floor'").fetchone()[0] == 0

    report = derive.derive_heights(project, estimate_floors=False)
    assert report.buildings_seen == 1, "extruded, counted, and still has no floors"
    assert report.floors_created == 4


def test_a_parcel_the_dem_does_not_cover_is_reported_not_skipped(project):
    """An ungrounded parcel keeps an absolute stratum, and that is not a quiet outcome.

    -30/+150 read absolutely over ground at 912 m puts the whole parcel column below its
    own buildings, so every structure on it raises ESCAPES_PARENT. Skipping the parcel
    without recording it turned a missing-raster problem into a wall of geometry errors
    three steps away, with `parcels_grounded` reporting only the ones that worked.
    """
    import shapely.geometry
    from cadastre.models import CreatedBy, Representation, Status, Unit, UnitType

    far = shapely.geometry.box(E + 9000, N + 9000, E + 9050, N + 9050)
    store.save_unit(project, Unit(
        unit_id="PCL-FAR", unit_type=UnitType.LAND_PARCEL, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008",
        footprint_2d=shapely.geometry.mapping(far), source_ids=["src"],
        created_by=CreatedBy.DERIVED, representation=Representation.PRISM,
        attributes={"parent_ulpin_14": PARENT}))
    project.commit()

    report = derive.derive_heights(project)
    assert report.parcels_ungrounded == ["PCL-FAR"]
    assert "PCL-FAR" in report.as_dict()["parcels_ungrounded"]
