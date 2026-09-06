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


# --- approving many at once, without hiding the refusals -------------------------------

@pytest.fixture
def bulk_client(tmp_path):
    """The bulk route over a real file, since it opens its own connection."""
    from cadastre.api import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    db = tmp_path / "bulk.gpkg"
    c = store.connect(str(db))
    store.init_schema(c)
    c.commit()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), str(db), c


def test_bulk_approve_reports_every_refusal_with_its_reason(bulk_client):
    """A summary that counts only successes buries the units that were refused.

    The guard refuses individual units for individual reasons, so "4,812 approved" over
    a project of 5,949 says nothing about the other 1,137 - and the reviewer's next
    action depends entirely on which reason applied.
    """
    client, db, conn = bulk_client
    ok, blocked = unit("U-OK"), unit("U-ERR")
    store.save_unit(conn, ok)
    store.save_unit(conn, blocked)
    store.save_run(conn, run_with("R-1", [
        finding("R-1", blocked.unit_id, Severity.ERROR, fid="F-ERR")]))
    conn.commit()

    r = client.post("/cadastre/units/transition", json={
        "db_path": db, "target_status": "approved", "actor": "reviewer"})
    assert r.status_code == 200, r.text
    got = r.json()

    assert got["attempted"] == 2
    assert got["approved"] == 1
    assert got["refused"] == 1
    assert sum(got["refused_by_reason"].values()) == 1
    assert [u["unit_id"] for u in got["units"]] == ["U-OK"]


def test_bulk_approve_keeps_the_units_it_could_approve(bulk_client):
    """One refusal must not roll back the rest; the approvable ones were the request."""
    client, db, conn = bulk_client
    for uid in ("U-1", "U-2", "U-3"):
        store.save_unit(conn, unit(uid))
    store.save_run(conn, run_with("R-1", [
        finding("R-1", "U-2", Severity.ERROR, fid="F-2")]))
    conn.commit()

    client.post("/cadastre/units/transition", json={
        "db_path": db, "target_status": "approved", "actor": "reviewer"})

    statuses = dict(conn.execute("SELECT unit_id, status FROM unit"))
    assert statuses["U-1"] == Status.APPROVED.value
    assert statuses["U-3"] == Status.APPROVED.value
    assert statuses["U-2"] == Status.NEEDS_REVIEW.value


def test_bulk_approve_without_a_validation_run_approves_nothing(bulk_client):
    """Fail closed in bulk exactly as it does one at a time."""
    client, db, conn = bulk_client
    for uid in ("U-1", "U-2"):
        store.save_unit(conn, unit(uid))
    conn.commit()

    got = client.post("/cadastre/units/transition", json={
        "db_path": db, "target_status": "approved", "actor": "reviewer"}).json()
    assert got["approved"] == 0
    assert got["refused"] == 2
    assert "no validation" in " ".join(got["refused_by_reason"])


def test_bulk_approve_can_be_given_an_explicit_list(bulk_client):
    """Approving a filtered view must not approve the units outside it."""
    client, db, conn = bulk_client
    for uid in ("U-1", "U-2"):
        store.save_unit(conn, unit(uid))
    store.save_run(conn, run_with("R-1", []))
    conn.commit()

    got = client.post("/cadastre/units/transition", json={
        "db_path": db, "target_status": "approved", "actor": "reviewer",
        "unit_ids": ["U-1"]}).json()
    assert got["attempted"] == 1 and got["approved"] == 1

    statuses = dict(conn.execute("SELECT unit_id, status FROM unit"))
    assert statuses["U-2"] == Status.NEEDS_REVIEW.value


def test_bulk_refusals_for_one_cause_group_into_one_reason(bulk_client):
    """The guard names the unit in its message, so the raw string groups nothing.

    Three units refused for the same cause came back as three distinct reasons, and the
    review screen rendered one line per unit: for a ward of 5,971 that is 884,000
    characters of the same sentence. Grouping exists so a reviewer reads a cause once.
    """
    client, db, conn = bulk_client
    for uid in ("U-1", "U-2", "U-3"):
        store.save_unit(conn, unit(uid))
    conn.commit()

    got = client.post("/cadastre/units/transition", json={
        "db_path": db, "target_status": "approved", "actor": "reviewer"}).json()
    assert got["refused"] == 3
    assert len(got["refused_by_reason"]) == 1, got["refused_by_reason"]
    assert list(got["refused_by_reason"].values()) == [3]
    assert not any(u in r for r in got["refused_by_reason"] for u in ("U-1", "U-2", "U-3"))
