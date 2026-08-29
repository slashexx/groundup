"""Validation run orchestration.

Builds one STRtree over all footprints in scope, then dispatches each rule module.
Findings belong to a run; the latest run for a unit determines its validation_state,
which gives us validation history for free.
"""

from __future__ import annotations

from ..models import Finding, Unit


def run(conn, units: list[Unit], settings, scope: str | None = None) -> tuple[str, list[Finding]]:
    """Execute every enabled rule over `units`. Returns (run_id, findings)."""
    raise NotImplementedError
