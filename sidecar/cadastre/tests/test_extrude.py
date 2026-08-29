"""Extrusion against rasters with known planted values.

Real pilot data is not chosen yet, and synthetic rasters are better than real ones for
this anyway: we know the ground truth exactly, so we can assert the algorithm recovers
it rather than merely producing something plausible.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from cadastre import validate
from cadastre.extrude import building as bld
from cadastre.extrude import floors as flr
from cadastre.extrude import raster, subdivide
from cadastre.models import CreatedBy, ProjectSettings, Relationship, RelType, UnitType
from shapely.geometry import box

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data/synthetic"
E, N = 445000.0, 1434000.0

# Values planted by tools/make_rasters.py
GROUND, SLAB, PARAPET, TANK = 912.4, 934.0, 935.0, 940.0
FOOTPRINT = box(E + 8, N + 6, E + 32, N + 24)


@pytest.fixture(scope="module", autouse=True)
def rasters():
    if not (DATA / "dem.tif").exists() or not (DATA / "dsm.tif").exists():
        subprocess.run([sys.executable, str(REPO / "sidecar/cadastre/tools/make_rasters.py")],
                       check=True, capture_output=True)
    return DATA / "dem.tif", DATA / "dsm.tif"


@pytest.fixture
def settings():
    return ProjectSettings(
        project_crs="EPSG:32643", vertical_datum="EGM2008",
        stratum_below_limit_m=-30.0, stratum_above_limit_m=150.0,
        default_plinth_offset_m=0.6,
        default_parapet_deduction_m=0.0,   # median estimator needs no parapet correction
        ulpin_version="v1", ruleset_version="r1",
    )


# --- estimator choice --------------------------------------------------------------

def test_ground_level_recovers_planted_truth(rasters):
    dem, _ = rasters
    assert raster.ground_level(dem, FOOTPRINT) == pytest.approx(GROUND, abs=0.05)


def test_roof_level_recovers_the_slab_not_the_parapet_or_the_tank(rasters):
    _, dsm = rasters
    assert raster.roof_level(dsm, FOOTPRINT) == pytest.approx(SLAB, abs=0.05)


def test_median_beats_every_alternative_estimator(rasters):
    """The reason raster.py uses median, asserted rather than asserted-in-a-comment.

    A DSM over a flat roof is bimodal - a large slab plane and a small parapet ring -
    plus point features like water tanks. Mean is dragged by them, p90 lands on the
    parapet, max lands on the tank. Only the median finds the dominant plane, and it
    does so regardless of building size.
    """
    _, dsm = rasters
    v = raster.sample(dsm, FOOTPRINT)
    err = lambda x: abs(x - SLAB)

    assert err(np.median(v)) < 0.05
    assert err(np.mean(v)) > err(np.median(v))
    assert err(np.percentile(v, 90)) > 0.5      # the parapet
    assert err(v.max()) > 5.0                    # the water tank
    assert v.max() == pytest.approx(TANK, abs=0.01)


def test_no_coverage_raises_rather_than_returning_a_default(rasters):
    """FR-03: missing data must be shown as missing, never invented."""
    dem, _ = rasters
    with pytest.raises(raster.NoCoverage):
        raster.ground_level(dem, box(E + 5000, N + 5000, E + 5010, N + 5010))


# --- building ----------------------------------------------------------------------

def test_building_spans_plinth_to_slab(rasters, settings):
    dem, dsm = rasters
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003", "SRC-004"], unit_id="BLD-T")
    assert b.lower_limit == pytest.approx(GROUND + 0.6, abs=0.05)
    assert b.upper_limit == pytest.approx(SLAB, abs=0.05)
    assert b.height == pytest.approx(21.0, abs=0.1)
    assert b.created_by is CreatedBy.DERIVED


def test_thin_coverage_leaves_heights_unknown_instead_of_guessing(rasters, settings):
    dem, dsm = rasters
    far = box(E + 85, N + 30, E + 200, N + 120)      # mostly outside the raster
    b = bld.build(far, dem, dsm, settings, ["SRC-003"], unit_id="BLD-EDGE")
    assert b.lower_limit is None and b.upper_limit is None
    assert "heights_unavailable" in b.attributes


def test_nonzero_parapet_deduction_is_refused(rasters, settings):
    """A stale project setting must fail loudly, not lower every floor in silence.

    The ingest contract carried default_parapet_deduction_m = 1.0 from before the roof
    estimator became a median. Accepting it puts every floor 1 m low and every storey
    14 cm short - and because all the relative relationships stay consistent, all 13
    validation rules still pass. That is the worst failure this block can produce.
    """
    dem, dsm = rasters
    settings.default_parapet_deduction_m = 1.0
    with pytest.raises(bld.EstimatorMismatch, match="median"):
        bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003"])


# --- floors ------------------------------------------------------------------------

def test_floors_are_contiguous_and_fill_the_building(rasters, settings):
    dem, dsm = rasters
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003", "SRC-004"], unit_id="BLD-T")
    fl = flr.split(b, floor_count=7, settings=settings)

    assert len(fl) == 7
    assert fl[0].lower_limit == pytest.approx(b.lower_limit)
    assert fl[-1].upper_limit == pytest.approx(b.upper_limit)
    for below, above in zip(fl, fl[1:]):
        assert below.upper_limit == pytest.approx(above.lower_limit, abs=1e-9)
    assert all(f.height == pytest.approx(3.0, abs=0.05) for f in fl)


def test_basements_get_negative_indices(rasters, settings):
    dem, dsm = rasters
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003"], unit_id="BLD-T")
    fl = flr.split(b, floor_count=7, settings=settings, basement_count=1)
    assert [f.attributes["floor_index"] for f in fl] == [-1, 0, 1, 2, 3, 4, 5, 6]


def test_building_without_heights_refuses_to_produce_floors(settings):
    from cadastre.models import Representation, Status, Unit
    b = Unit(unit_id="X", unit_type=UnitType.BUILDING, status=Status.DRAFT,
             crs="EPSG:32643", vertical_datum="EGM2008",
             footprint_2d=FOOTPRINT.__geo_interface__, source_ids=["s"],
             created_by=CreatedBy.DERIVED, representation=Representation.PRISM)
    with pytest.raises(flr.NotExtrudable):
        flr.split(b, floor_count=5, settings=settings)


def test_implausible_storey_heights_are_flagged_not_corrected(rasters, settings):
    dem, dsm = rasters
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003"], unit_id="BLD-T")
    assert flr.implausible(flr.split(b, 7, settings), settings) == []
    assert flr.implausible(flr.split(b, 2, settings), settings)   # 10.5 m storeys


# --- subdivision -------------------------------------------------------------------

def test_apartments_inherit_the_floor_z_range_exactly(rasters, settings):
    dem, dsm = rasters
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003"], unit_id="BLD-T")
    floor = flr.split(b, 7, settings)[1]
    plan = [box(E + 8, N + 6, E + 20, N + 24), box(E + 20, N + 6, E + 32, N + 24)]
    apts = subdivide.from_plan(floor, plan, ["SRC-005"], confidence=0.5)

    assert len(apts) == 2
    assert all(a.lower_limit == floor.lower_limit for a in apts)
    assert all(a.upper_limit == floor.upper_limit for a in apts)
    assert floor.attributes["subdivided"] is True


def test_floors_default_to_unsubdivided(rasters, settings):
    dem, dsm = rasters
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003"], unit_id="BLD-T")
    assert all(f.attributes["subdivided"] is False for f in flr.split(b, 7, settings))


# --- the integration that matters --------------------------------------------------

def test_extruded_geometry_passes_our_own_validation(rasters, settings):
    """Extrude a whole building and run the validator over it. Zero findings.

    This closes the loop: the geometry we generate must satisfy the rules we enforce.
    If extrusion and validation ever disagree, one of them is wrong.
    """
    dem, dsm = rasters
    parcel_geom = box(E, N, E + 40, N + 30)
    b = bld.build(FOOTPRINT, dem, dsm, settings, ["SRC-003", "SRC-004"], unit_id="BLD-T")
    fl = flr.split(b, floor_count=7, settings=settings)
    floor = fl[1]
    apts = subdivide.from_plan(
        floor, [box(E + 8, N + 6, E + 20, N + 24), box(E + 20, N + 6, E + 32, N + 24)],
        ["SRC-005"], confidence=0.8)

    from cadastre.models import CreatedBy as CB
    from cadastre.models import Representation, Status, Unit
    parcel = Unit(unit_id="PCL-T", unit_type=UnitType.LAND_PARCEL, status=Status.DRAFT,
                  crs="EPSG:32643", vertical_datum="EGM2008",
                  footprint_2d=parcel_geom.__geo_interface__, source_ids=["SRC-001"],
                  created_by=CB.HUMAN, representation=Representation.PRISM,
                  lower_limit=GROUND - 30, upper_limit=GROUND + 150)

    units = [parcel, b, *fl, *apts]
    rels = [Relationship("PCL-T", "BLD-T", RelType.CONTAINS, None)]
    rels += [Relationship("BLD-T", f.unit_id, RelType.CONTAINS, None) for f in fl]
    rels += [Relationship(floor.unit_id, a.unit_id, RelType.CONTAINS, None) for a in apts]

    from cadastre.models import Accuracy
    sources = {"SRC-001": Accuracy(0.30, 0.50), "SRC-003": Accuracy(0.20, 0.10),
               "SRC-004": Accuracy(0.20, 0.10), "SRC-005": Accuracy(0.05, 0.05)}

    result = validate.run(units, rels, sources, settings)
    assert result.findings == [], [
        f"{f.severity.value} {f.rule_id.value} on {f.unit_id}: {f.message}"
        for f in result.findings]
