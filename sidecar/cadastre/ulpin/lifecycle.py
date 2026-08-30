"""Record lifecycle (FR-09).

    draft -> processing -> needs_review -> approved -> replaced
      ^          |              |             |
      +--(fail)--+              |             +---------> closed
      +---(reject + comment)----+

The one transition that matters: needs_review -> approved is guarded on zero Error
findings AND every Warning acknowledged, and its side effect is freezing the ULPIN.
An approved record is never edited; any change creates a new version.
"""

import sqlite3

from .. import store
from ..models import Status, Unit
from . import ledger

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.DRAFT: frozenset({Status.PROCESSING}),
    Status.PROCESSING: frozenset({Status.NEEDS_REVIEW, Status.DRAFT}),
    Status.NEEDS_REVIEW: frozenset({Status.APPROVED, Status.DRAFT}),
    Status.APPROVED: frozenset({Status.REPLACED, Status.CLOSED}),
    Status.REPLACED: frozenset(),
    Status.CLOSED: frozenset(),
}


class TransitionError(Exception):
    """Raised when a transition is not permitted, or its guard is unmet."""


def can_transition(current: Status, target: Status) -> bool:
    return target in TRANSITIONS[current]


def transition(
    conn: sqlite3.Connection,
    unit: Unit,
    target: Status | str,
    actor: str,
    comment: str | None = None,
    validation_run=None,
) -> None:
    """Move a unit to `target`, enforcing the guard and running the side effect."""
    current = unit.status
    target_status = Status(target) if isinstance(target, str) else target

    if not can_transition(current, target_status):
        raise TransitionError(f"Cannot transition from {current.value} to {target_status.value}")

    if target_status == Status.APPROVED:
        # Fail closed. An absent validation run means "we cannot verify this unit", not
        # "there is nothing to verify" - treating it as permission previously allowed a
        # unit whose validation had FAILED to be approved with a permanent identifier.
        run = validation_run if validation_run is not None else store.load_latest_run(conn)
        if run is None:
            raise TransitionError(
                f"{unit.unit_id} cannot be approved: no validation run has been recorded. "
                "Run validation and persist it before approving.")
        if not run.approvable(unit.unit_id):
            blocking = [
                f"{f.severity.value} {f.rule_id.value}"
                for f in run.for_unit(unit.unit_id)
                if f.severity.value == "error"
                or (f.severity.value == "warning" and f.acknowledged_by is None)
            ]
            raise TransitionError(
                f"{unit.unit_id} cannot be approved: {', '.join(blocking)}. "
                "Errors must be fixed and revalidated; warnings must be acknowledged.")
        ledger.freeze(conn, unit)
    else:
        cur = conn.cursor()
        cur.execute("UPDATE unit SET status = ? WHERE unit_id = ?", (target_status.value, unit.unit_id))
        conn.commit()
        unit.status = target_status

