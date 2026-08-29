"""Shared helpers for rule modules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ...models import Finding, RuleId, Severity


def finding(run_id: str, rule: RuleId, severity: Severity, unit_id: str, message: str,
            *, related: list[str] | None = None, geometry=None,
            measured: float | None = None, tolerance: float | None = None,
            action: str | None = None) -> Finding:
    return Finding(
        finding_id=str(uuid.uuid4()), run_id=run_id, rule_id=rule, severity=severity,
        unit_id=unit_id, message=message, detected_at=datetime.now(UTC),
        related_unit_ids=related or [], affected_geometry=geometry,
        measured_value=measured, tolerance=tolerance, suggested_action=action,
    )


def z_overlap(a, b, tol_v: float) -> bool:
    """True when two z-intervals genuinely overlap, beyond vertical measurement error.

    Touching intervals (one floor's ceiling is the next one's floor) are NOT an overlap.
    """
    if None in (a.lower_limit, a.upper_limit, b.lower_limit, b.upper_limit):
        return False
    return max(a.lower_limit, b.lower_limit) < min(a.upper_limit, b.upper_limit) - tol_v


def shrink(geom, tol: float):
    """Erode a footprint by the tolerance so a shared boundary stops counting as contact.

    Returns the original geometry if erosion would annihilate it - a unit smaller than
    its own measurement error cannot be meaningfully compared, and PROVENANCE/accuracy
    findings are the right channel for that, not a silent pass.
    """
    if tol <= 0:
        return geom
    small = geom.buffer(-tol)
    return geom if small.is_empty else small
