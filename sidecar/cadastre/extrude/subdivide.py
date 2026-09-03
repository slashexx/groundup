"""Floor -> apartment units.

We usually have no interior geometry. In order of preference:

1. a floor plan exists -> vectorise and apply. A repeating tower may reuse one plan
   across floors; mark created_by=DERIVED, low confidence, requires review.
2. manual delineation in the UI.
3. nothing -> do NOT create apartment units. Set attributes["subdivided"] = False.

Path 3 is the default and it is what FR-03 requires. Fabricating apartments across a
dataset is the fastest way to lose a reviewer who knows this domain, and it makes every
downstream ownership claim untraceable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from ..models import CreatedBy, Representation, Status, Unit, UnitType
from .floors import INHERITED


def from_plan(floor: Unit, plan_geoms: list[BaseGeometry], source_ids: list[str],
              *, confidence: float | None = None) -> list[Unit]:
    """Apply vectorised floor-plan polygons to one floor.

    The apartments inherit the floor's z-range exactly, so a subdivision can never
    escape its parent vertically.
    """
    now = datetime.now(UTC)
    outline = shape(floor.footprint_2d)
    units = []
    for geom in plan_geoms:
        clipped = geom.intersection(outline)
        if clipped.is_empty:
            continue
        units.append(Unit(
            unit_id=str(uuid.uuid4()),
            unit_type=UnitType.APARTMENT,
            status=Status.NEEDS_REVIEW,
            crs=floor.crs,
            vertical_datum=floor.vertical_datum,
            footprint_2d=clipped.__geo_interface__,
            source_ids=list(source_ids),
            created_by=CreatedBy.DERIVED,
            representation=Representation.PRISM,
            lower_limit=floor.lower_limit,
            upper_limit=floor.upper_limit,
            confidence_score=confidence,
            recorded_from=now,
            attributes={k: v for k, v in floor.attributes.items() if k in INHERITED}
            | {"floor_index": floor.attributes.get("floor_index")},
        ))
    if units:
        floor.attributes["subdivided"] = True
    return units


def mark_unsubdivided(floor: Unit) -> Unit:
    """Record honestly that this floor has no interior data.

    Validation reads this flag: a floor that makes no tiling claim is not gap-checked.
    """
    floor.attributes["subdivided"] = False
    return floor
