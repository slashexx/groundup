"""Validation run orchestration.

Rules are pure functions of (Context, run_id) returning findings. Registering one here is
the only wiring needed. Cheap rules run first so an obviously broken unit surfaces before
the expensive spatial work.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from ..models import Finding, ProjectSettings, Relationship, Severity, Unit, ValidationState
from . import context as ctx_mod
from .rules import containment, geometry, metadata, overlap, sequence

Rule = Callable[[ctx_mod.Context, str], list[Finding]]

#: Order matters only for readability of output; rules are independent.
RULES: tuple[tuple[str, Rule], ...] = (
    ("geometry.invalid", geometry.invalid),
    ("geometry.impossible_z", geometry.impossible_z),
    ("geometry.duplicate", geometry.duplicate),
    ("metadata.crs_mismatch", metadata.crs_mismatch),
    ("metadata.datum_mismatch", metadata.datum_mismatch),
    ("metadata.provenance_missing", metadata.provenance_missing),
    ("metadata.confidence_low", metadata.confidence_low),
    ("sequence.floor_sequence", sequence.floor_sequence),
    ("sequence.floor_height_plausible", sequence.floor_height_plausible),
    ("overlap.siblings_overlap", overlap.siblings_overlap),
    ("overlap.gap_against_parent", overlap.gap_against_parent),
    ("containment.escapes_parent", containment.escapes_parent),
    ("containment.utility_crosses_building", containment.utility_crosses_building),
)


@dataclass
class ValidationRun:
    run_id: str
    started_at: datetime
    finished_at: datetime
    ruleset_version: str
    findings: list[Finding]

    def for_unit(self, unit_id: str) -> list[Finding]:
        return [f for f in self.findings
                if f.unit_id == unit_id or unit_id in f.related_unit_ids]

    def state_of(self, unit_id: str) -> ValidationState:
        """A unit's validation state is decided by the worst finding naming it."""
        sev = {f.severity for f in self.for_unit(unit_id)}
        if Severity.ERROR in sev:
            return ValidationState.FAILED
        if Severity.WARNING in sev:
            return ValidationState.PASSED_WITH_WARNINGS
        return ValidationState.PASSED

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    def approvable(self, unit_id: str) -> bool:
        """Guard for needs_review -> approved. Errors block; warnings need acknowledgement."""
        for f in self.for_unit(unit_id):
            if f.severity is Severity.ERROR:
                return False
            if f.severity is Severity.WARNING and f.acknowledged_by is None:
                return False
        return True


def run(units: list[Unit], relationships: list[Relationship],
        sources: dict, settings: ProjectSettings,
        rules: tuple[tuple[str, Rule], ...] = RULES) -> ValidationRun:
    started = datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())
    ctx = ctx_mod.build(units, relationships, sources, settings)

    findings: list[Finding] = []
    for _, fn in rules:
        findings.extend(fn(ctx, run_id))

    return ValidationRun(run_id=run_id, started_at=started,
                         finished_at=datetime.now(timezone.utc),
                         ruleset_version=settings.ruleset_version, findings=findings)
