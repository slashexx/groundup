"""Floor ordering and contiguity.

Sorted by floor_index, each floor's upper_limit must meet the next floor's lower_limit
within the vertical tolerance. A gap or an inversion means the height model is wrong.
"""

from __future__ import annotations

from ...models import Finding, Unit


def floor_sequence(units: list[Unit], ctx) -> list[Finding]:
    raise NotImplementedError


def floor_height_plausible(units: list[Unit], ctx) -> list[Finding]:
    """Outside settings.min/max_floor_height_m -> Warning."""
    raise NotImplementedError
