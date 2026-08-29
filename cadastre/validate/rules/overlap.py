"""Sibling overlap and gap detection.

No 3D boolean engine is needed, because every unit is a prism:

    two units intersect  iff  footprints intersect  AND  z-intervals overlap

The inward buffer by the horizontal tolerance is what separates a shared wall (normal,
adjacent flats touch by definition) from real penetration (a finding).

The gap check is a WARNING, not an error. Corridors, lift shafts and stairwells
legitimately leave gaps when only apartments are modelled; erroring here would flag
every real building.
"""

from __future__ import annotations

from ...models import Finding, Unit


def z_overlap(a: Unit, b: Unit, tol_v: float) -> bool:
    if None in (a.lower_limit, a.upper_limit, b.lower_limit, b.upper_limit):
        return False
    return max(a.lower_limit, b.lower_limit) < min(a.upper_limit, b.upper_limit) - tol_v


def siblings_overlap(units: list[Unit], ctx) -> list[Finding]:
    """STRtree candidates -> z-interval test -> buffered footprint intersection."""
    raise NotImplementedError


def gap_against_parent(units: list[Unit], ctx) -> list[Finding]:
    """parent.difference(union(children)).area beyond tolerance."""
    raise NotImplementedError
