"""Footprint + DEM/DSM -> a building unit."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from shapely.geometry.base import BaseGeometry

from ..models import CreatedBy, ProjectSettings, Representation, Status, Unit, UnitType
from . import raster

#: Below this fraction of valid pixels we refuse to derive heights rather than average
#: a handful of them into a confident-looking number.
MIN_COVERAGE = 0.6


def build(footprint: BaseGeometry, dem_path: str, dsm_path: str,
          settings: ProjectSettings, source_ids: list[str],
          *, unit_id: str | None = None, floor_count: int | None = None) -> Unit:
    """Create a building unit spanning ground level to the roof slab.

    Heights are left as None when raster coverage is too thin. That is FR-03: missing
    data is shown as missing, never guessed.
    """
    cover = min(raster.coverage(dem_path, footprint), raster.coverage(dsm_path, footprint))
    attrs: dict = {"raster_coverage": round(cover, 3)}

    if cover >= MIN_COVERAGE:
        ground = raster.ground_level(dem_path, footprint)
        roof = raster.roof_level(dsm_path, footprint)
        base = ground + settings.default_plinth_offset_m
        top = roof - settings.default_parapet_deduction_m
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
        recorded_from=datetime.now(timezone.utc),
        attributes=attrs,
    )
