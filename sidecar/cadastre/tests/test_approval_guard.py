"""Approval is the one irreversible transition, so it is tested adversarially.

Crossing needs_review -> approved freezes an identifier permanently. Everything before it
is provisional and freely recomputed; everything after it is a claim about real property.
The guard on that boundary must fail closed: when validation cannot be verified, the
answer is refusal, not permission.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cadastre import store, validate
from cadastre.models import (
    CreatedBy,
    Finding,
    RuleId,
    Severity,
    Status,
    Unit,
    UnitType,
    ValidationState,
)
from cadastre.ulpin import lifecycle

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
PARENT = "KA05B012345678"


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    store.init_schema(c)
    return c


def unit(uid="U-1", state=ValidationState.UNVALIDATED) -> Unit:
    return Unit(
        unit_id=uid, unit_type=UnitType.APARTMENT, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008", footprint_2d=SQUARE,
        source_ids=["SRC-005"], created_by=CreatedBy.HUMAN, ulpin_version="v1",
        validation_state=state, recorded_from=datetime.now(UTC),
        attributes={"floor_index": 1, "parent_ulpin_14": PARENT},
    )


def finding(run_id, uid, severity, rule=RuleId.OVERLAP_SIBLING, fid="F-1") -> Finding:
    return Finding(finding_id=fid, run_id=run_id, rule_id=rule, severity=severity,
                   unit_id=uid, message="planted", detected_at=datetime.now(UTC))


def run_with(run_id, findings) -> validate.ValidationRun:
    now = datetime.now(UTC)
    return validate.ValidationRun(run_id=run_id, started_at=now, finished_at=now,
                                  ruleset_version="r1", findings=findings)


# --- fail closed ------------------------------------------------------------------

def test_approval_is_refused_when_no_validation_has_been_recorded(conn):
    """The bug this file exists for.

    An absent validation run means "we cannot verify this", not "there is nothing to
    verify". Treating it as permission let a unit whose validation had FAILED be approved
    with a frozen, permanent identifier.
    """
    u = unit(state=ValidationState.FAILED)
    store.save_unit(conn, u)
    with pytest.raises(lifecycle.TransitionError, match="no validation"):
        lifecycle.transition(conn, u, Status.APPROVED, actor="anyone")
    assert u.status is Status.NEEDS_REVIEW
    assert u.ulpin is None


def test_errors_block_approval(conn):
    u = unit()
    store.save_unit(conn, u)
    store.save_run(conn, run_with("R-1", [finding("R-1", u.unit_id, Severity.ERROR)]))
    with pytest.raises(lifecycle.TransitionError):
        lifecycle.transition(conn, u, Status.APPROVED, actor="reviewer")


def test_unacknowledged_warnings_block_approval(conn):
    u = unit()
    store.save_unit(conn, u)
    store.save_run(conn, run_with("R-1", [finding("R-1", u.unit_id, Severity.WARNING)]))
    with pytest.raises(lifecycle.TransitionError):
        lifecycle.transition(conn, u, Status.APPROVED, actor="reviewer")

    store.acknowledge_finding(conn, "F-1", "reviewer")
    lifecycle.transition(conn, u, Status.APPROVED, actor="reviewer")
    assert u.status is Status.APPROVED and u.ulpin


def test_a_clean_run_permits_approval(conn):
    u = unit()
    store.save_unit(conn, u)
    store.save_run(conn, run_with("R-1", []))
    lifecycle.transition(conn, u, Status.APPROVED, actor="reviewer")
    assert u.ulpin and store.get_unit(conn, u.unit_id).status is Status.APPROVED


def test_only_the_latest_run_counts(conn):
    """Re-running validation after a fix must be able to clear an earlier error."""
    u = unit()
    store.save_unit(conn, u)
    store.save_run(conn, run_with("R-1", [finding("R-1", u.unit_id, Severity.ERROR)]))
    store.save_run(conn, run_with("R-2", []))
    lifecycle.transition(conn, u, Status.APPROVED, actor="reviewer")
    assert u.status is Status.APPROVED


# --- persistence ------------------------------------------------------------------

def test_findings_survive_a_reconnect(conn):
    f = finding("R-1", "U-1", Severity.WARNING)
    f.measured_value, f.tolerance = 7.2, 0.071
    store.save_run(conn, run_with("R-1", [f]))

    back = store.load_latest_run(conn)
    assert back.run_id == "R-1" and len(back.findings) == 1
    got = back.findings[0]
    assert (got.rule_id, got.severity) == (RuleId.OVERLAP_SIBLING, Severity.WARNING)
    assert (got.measured_value, got.tolerance) == (7.2, 0.071)


def test_acknowledgement_is_recorded_against_the_finding(conn):
    store.save_run(conn, run_with("R-1", [finding("R-1", "U-1", Severity.WARNING)]))
    store.acknowledge_finding(conn, "F-1", "dhruv")
    got = store.load_latest_run(conn).findings[0]
    assert got.acknowledged_by == "dhruv" and got.acknowledged_at is not None


def test_a_real_validation_run_round_trips(conn, bundle):
    """The fixture's five findings, persisted and read back intact."""
    result = validate.run(bundle["units"], bundle["relationships"],
                          bundle["sources"], bundle["settings"])
    store.save_run(conn, result)
    back = store.load_latest_run(conn)
    assert len(back.findings) == len(result.findings) == 5
    assert {(f.rule_id, f.unit_id) for f in back.findings} == \
           {(f.rule_id, f.unit_id) for f in result.findings}
    assert not back.approvable("APT-102")
