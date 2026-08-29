"""Building -> N floor units.

    usable       = roof_slab - (ground + plinth_offset)
    floor_height = usable / floor_count

The plinth correction is specifically right for Indian construction: buildings sit
0.3-1.0 m above the surrounding ground, so the ground floor slab is not at DEM level.
It is a project parameter, not a constant.

There is deliberately no parapet correction here - `raster.roof_level` returns the
dominant roof plane rather than a high percentile, so the parapet was never included.
`default_parapet_deduction_m` is retained in settings as an escape hatch for sloped
roofs and should be 0.0 for the median estimator.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shapely.geometry import shape

from ..models import CreatedBy, ProjectSettings, Representation, Status, Unit, UnitType


class NotExtrudable(ValueError):
    """The building has no usable height range, so floors cannot be derived."""


def split(building: Unit, floor_count: int, settings: ProjectSettings,
          *, basement_count: int = 0) -> list[Unit]:
    """Slice a building into contiguous floors. Ground floor is floor_index 0.

    Floors are generated contiguously by construction: each floor's upper limit is the
    next one's lower limit, computed from a single base rather than accumulated, so
    `FLOOR_SEQUENCE` cannot fail on rounding drift.
    """
    if floor_count < 1:
        raise NotExtrudable(f"floor_count must be at least 1, got {floor_count}")
    if building.lower_limit is None or building.upper_limit is None:
        raise NotExtrudable(
            f"{building.unit_id} has no height range; heights were not derivable from "
            "the rasters and must not be invented")

    total = floor_count + basement_count
    height = (building.upper_limit - building.lower_limit) / total
    now = datetime.now(UTC)
    geom = shape(building.footprint_2d)

    floors = []
    for i in range(total):
        index = i - basement_count                      # basements are negative
        lower = building.lower_limit + i * height
        floors.append(Unit(
            unit_id=str(uuid.uuid4()),
            unit_type=UnitType.FLOOR,
            status=Status.NEEDS_REVIEW,
            crs=building.crs,
            vertical_datum=building.vertical_datum,
            footprint_2d=geom.__geo_interface__,
            source_ids=list(building.source_ids),
            created_by=CreatedBy.DERIVED,
            representation=Representation.PRISM,
            lower_limit=lower,
            upper_limit=lower + height,
            confidence_score=building.confidence_score,
            recorded_from=now,
            attributes={"floor_index": index,
                        "floor_height_m": round(height, 3),
                        "subdivided": False},
        ))
    return floors


def implausible(floors: list[Unit], settings: ProjectSettings) -> list[Unit]:
    """Floors outside the plausible storey-height band.

    Reported, never silently corrected - validation raises the warning and a human
    decides. A 5.5 m ground floor is entirely normal for retail.
    """
    return [f for f in floors if f.height is not None
            and not (settings.min_floor_height_m <= f.height <= settings.max_floor_height_m)]
