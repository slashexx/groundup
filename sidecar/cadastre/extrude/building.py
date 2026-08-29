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

    cover = min(raster.coverage(dem_path, footprint), raster.coverage(dsm_path, footprint))
    attrs: dict = {"raster_coverage": round(cover, 3)}

    if cover >= MIN_COVERAGE:
        ground = raster.ground_level(dem_path, footprint)
        roof = raster.roof_level(dsm_path, footprint)
        base = ground + settings.default_plinth_offset_m
        top = roof
        attrs |= {"ground_level_m": round(ground, 3), "roof_level_m": round(roof, 3),
                  "plinth_offset_m": settings.default_plinth_offset_m}
    else:
        base = top = None
        attrs["heights_unavailable"] = "raster coverage below threshold"

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
