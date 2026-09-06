"""Footprint + DEM/DSM -> a building unit."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shapely.geometry.base import BaseGeometry

from ..models import CreatedBy, ProjectSettings, Representation, Status, Unit, UnitType
from . import raster

#: Below this fraction of valid pixels we refuse to derive heights rather than average
#: a handful of them into a confident-looking number.
MIN_COVERAGE = 0.6

#: And below this many cells, whatever the fraction says.
#:
#: A fraction cannot express "this raster is too coarse for this building". A 20 m2
#: footprint on a 5 m DEM covers less than one cell, so one valid pixel is 100% coverage
#: and the median of one number is that number - published as a measured roof level, with
#: nothing recording that it came from a single sample. Nine cells is a 3x3 neighbourhood,
#: the smallest window in which a median means anything at all.
MIN_VALID_PIXELS = 9


class EstimatorMismatch(ValueError):
    """The project asks for a parapet deduction the roof estimator does not need.

    `raster.roof_level` is a MEDIAN, which finds the dominant roof plane directly - the
    parapet is already rejected as a minority. Subtracting a deduction on top of that
    lowers every floor in the building by that amount, and because all the relative
    relationships stay consistent, every validation rule still passes. Silent, plausible
    and wrong is the worst failure this block can produce, so it is refused loudly here
    rather than documented and hoped for.

    The setting is retained for a future percentile-based estimator on sloped roofs.
    """


def build(footprint: BaseGeometry, dem_path: str, dsm_path: str,
          settings: ProjectSettings, source_ids: list[str],
          *, unit_id: str | None = None, floor_count: int | None = None) -> Unit:
    """Create a building unit spanning ground level to the roof slab.

    Heights are left as None when raster coverage is too thin. That is FR-03: missing
    data is shown as missing, never guessed.
    """
    if settings.default_parapet_deduction_m:
        raise EstimatorMismatch(
            f"default_parapet_deduction_m is {settings.default_parapet_deduction_m}, but "
            "roof_level uses a median estimator that already returns the roof slab. "
            "Applying the deduction would lower every floor by that amount with nothing "
            "reporting it. Set default_parapet_deduction_m to 0.0 in project_settings.")

    # The footprint is in the project CRS; the rasters may be in any. Saying so is what
    # lets `raster` reproject rather than assume they agree.
    crs = settings.project_crs
    cover = min(raster.coverage(dem_path, footprint, crs),
                raster.coverage(dsm_path, footprint, crs))
    cells = min(raster.valid_pixels(dem_path, footprint, crs),
                raster.valid_pixels(dsm_path, footprint, crs))
    attrs: dict = {"raster_coverage": round(cover, 3), "raster_cells": cells}

    if cover >= MIN_COVERAGE and cells >= MIN_VALID_PIXELS:
        ground = raster.ground_level(dem_path, footprint, crs)
        roof = raster.roof_level(dsm_path, footprint, crs)
        base = ground + settings.default_plinth_offset_m
        top = roof
        attrs |= {"ground_level_m": round(ground, 3), "roof_level_m": round(roof, 3),
                  "plinth_offset_m": settings.default_plinth_offset_m}
    else:
        base = top = None
        attrs["heights_unavailable"] = (
            f"only {cells} valid raster cell(s) under this footprint "
            f"({cover:.1%} coverage). A median needs more than a handful of samples, "
            f"so the height is left unknown rather than measured from {cells}."
            if cells < MIN_VALID_PIXELS else
            f"raster coverage {cover:.1%} is below the {MIN_COVERAGE:.0%} threshold. "
            "The rasters do not cover enough of this footprint to measure it.")

    if floor_count is not None:
        attrs["floor_count"] = floor_count

    return Unit(
        unit_id=unit_id or str(uuid.uuid4()),
        unit_type=UnitType.BUILDING,
        status=Status.NEEDS_REVIEW,
        crs=settings.project_crs,
        vertical_datum=settings.vertical_datum,
        footprint_2d=footprint.__geo_interface__,
        source_ids=list(source_ids),
        created_by=CreatedBy.DERIVED,
        representation=Representation.PRISM,
        lower_limit=base,
        upper_limit=top,
        recorded_from=datetime.now(UTC),
        attributes=attrs,
    )
