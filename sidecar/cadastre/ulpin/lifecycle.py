"""Record lifecycle (FR-09).

    draft -> processing -> needs_review -> approved -> replaced
      ^          |              |             |
      +--(fail)--+              |             +---------> closed
      +---(reject + comment)----+

The one transition that matters: needs_review -> approved is guarded on zero Error
findings AND every Warning acknowledged, and its side effect is freezing the ULPIN.
An approved record is never edited; any change creates a new version.
"""

from __future__ import annotations

from ..models import Status

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


def transition(conn, unit_id: str, target: Status, actor: str, comment: str | None = None):
    """Move a unit to `target`, enforcing the guard and running the side effect."""
    raise NotImplementedError
