"""Comparison tolerances derived from source accuracy.

    tol = k * sqrt(acc_a^2 + acc_b^2)

Never hardcode a tolerance constant. If a footprint came from a survey with 30 cm
accuracy, a 5 cm overlap with its neighbour is measurement noise, not an encroachment.
Reporting it wastes reviewer attention and trains people to click through warnings,
which destroys the human-in-the-loop guarantee the whole system rests on.

Accuracy values come from the ingest block's source registry, per unit, via source_ids.
They are mandatory there for exactly this reason.
"""

from __future__ import annotations

import math

from ..models import Accuracy, Unit


def combined(a: Accuracy, b: Accuracy, k: float = 1.0) -> tuple[float, float]:
    """Horizontal and vertical tolerance for comparing two measurements.

    k = 1.0 is one sigma; use 1.96 for a 95% confidence band.
    """
    return (
        k * math.hypot(a.horizontal_m, b.horizontal_m),
        k * math.hypot(a.vertical_m, b.vertical_m),
    )


def for_unit(conn, unit: Unit) -> Accuracy:
    """Worst-case accuracy across every source that contributed to this unit."""
    raise NotImplementedError


def area_tolerance(tol_h: float, shared_edge_length: float) -> float:
    """Overlap area below this is attributable to horizontal measurement error."""
    return tol_h * shared_edge_length
