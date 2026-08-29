"""Per-unit geometric sanity. Cheap - safe to run on every save."""

from __future__ import annotations

from ...models import Finding, Unit


def invalid(units: list[Unit], ctx) -> list[Finding]:
    """shapely.is_valid: self-intersection, duplicate points, unclosed rings."""
    raise NotImplementedError


def impossible_z(units: list[Unit], ctx) -> list[Finding]:
    """lower_limit >= upper_limit."""
    raise NotImplementedError


def duplicate(units: list[Unit], ctx) -> list[Finding]:
    """Normalised WKB hash plus matching z-range."""
    raise NotImplementedError
