"""Building -> N floor units.

    usable = (roof - parapet_deduction) - (ground + plinth_offset)
    floor_height = usable / floor_count

Both corrections are specifically right for Indian construction and both are project
parameters, not constants:

* **plinth_offset** - buildings sit 0.3-1.0 m above surrounding ground, so the ground
  floor slab is not at DEM level
* **parapet_deduction** - the DSM roof includes a ~1 m parapet wall; without this every
  floor comes out systematically short

A resulting floor height outside `settings.min/max_floor_height_m` emits a Warning
rather than being silently accepted or silently corrected.
"""

from __future__ import annotations

from ..models import ProjectSettings, Unit


def split(building: Unit, floor_count: int, settings: ProjectSettings) -> list[Unit]:
    """Slice a building into contiguous floor units, ground floor at floor_index 0."""
    raise NotImplementedError
