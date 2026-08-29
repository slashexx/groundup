"""Parent containment - type-conditional.

Underground and elevated units are easements, not ownership volumes. Crossing a parcel
boundary is normal and expected for them; a tunnel confined to a single parcel would be
the anomaly. Crossing a *building volume* is still an error - a water main through
someone's flat.

Ownership volumes must not overlap. Easement corridors are supposed to.
See models.UnitType.is_easement.
"""

from __future__ import annotations

from ...models import Finding, Unit


def escapes_parent(units: list[Unit], ctx) -> list[Finding]:
    raise NotImplementedError


def utility_crosses_building(units: list[Unit], ctx) -> list[Finding]:
    raise NotImplementedError
