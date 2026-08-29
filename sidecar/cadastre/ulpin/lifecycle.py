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
        if validation_run is not None and not validation_run.approvable(unit.unit_id):
            raise TransitionError(
                f"Unit {unit.unit_id} cannot be approved: unacknowledged warnings or error findings exist."
            )
        ledger.freeze(conn, unit)
    else:
        cur = conn.cursor()
        cur.execute("UPDATE unit SET status = ? WHERE unit_id = ?", (target_status.value, unit.unit_id))
        conn.commit()
        unit.status = target_status

