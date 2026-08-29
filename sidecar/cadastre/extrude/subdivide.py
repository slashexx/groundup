"""Floor -> apartment units.

We usually have no interior geometry. Three paths, in order of preference:

1. a floor plan exists -> vectorise and apply (a repeating tower may reuse one plan
   across floors; mark created_by=DERIVED, low confidence, requires review)
2. manual delineation in the UI
3. nothing -> do NOT create apartment units; set attributes["subdivided"] = False

Path 3 is the default and it is what FR-03 requires: the system must show missing data
as missing rather than quietly guessing it.
"""

from __future__ import annotations

from ..models import Unit


def from_floor_plan(floor: Unit, plan_geoms: list, source_ids: list[str]) -> list[Unit]:
    raise NotImplementedError


def mark_unsubdivided(floor: Unit) -> Unit:
    """Record honestly that this floor has no interior data."""
    floor.attributes["subdivided"] = False
    return floor
