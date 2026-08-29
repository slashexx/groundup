"""Comparison tolerances derived from source accuracy.

    tol = k * sqrt(acc_a^2 + acc_b^2)

Never hardcode a tolerance constant. If a footprint was captured at 30 cm accuracy, a
5 cm overlap with its neighbour is measurement noise, not an encroachment. Reporting it
wastes reviewer attention and trains people to click through warnings, which destroys the
human-in-the-loop guarantee the whole system rests on.
"""

from __future__ import annotations

import math

from ..models import Accuracy


def combined(a: Accuracy, b: Accuracy, k: float = 1.0) -> tuple[float, float]:
    """Horizontal and vertical tolerance for comparing two measurements.

    k = 1.0 is one sigma; use 1.96 for a 95% confidence band.
    """
    return k * math.hypot(a.horizontal_m, b.horizontal_m), k * math.hypot(a.vertical_m, b.vertical_m)


def pair(ctx, a_id: str, b_id: str) -> tuple[float, float]:
    return combined(ctx.accuracy[a_id], ctx.accuracy[b_id], ctx.settings.tolerance_k)


def self_(ctx, unit_id: str) -> tuple[float, float]:
    """Tolerance for comparing a unit against itself or a derived quantity."""
    return combined(ctx.accuracy[unit_id], ctx.accuracy[unit_id], ctx.settings.tolerance_k)


def negligible_area(tol_h: float) -> float:
    """Area below which a leftover sliver is measurement noise, not a real conflict.

    A square of side `tol_h`. Deliberately NOT scaled by perimeter: a long thin corridor
    has a huge perimeter, and a perimeter-scaled allowance would let a 90 m utility line
    escape its parcel by 40 m2 unremarked. Callers erode the geometry by `tol_h` first,
    so tolerance is already absorbed morphologically - this threshold only rejects
    floating-point residue.
    """
    return max(tol_h ** 2, 1e-9)
