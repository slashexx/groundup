"""ULPIN allocation and the non-reuse guarantee (FR-06).

The ledger is the reason an issued ULPIN can never be handed to another unit, even
after the original is closed. Rows are appended, never deleted.

It is also where the determinism trap is defused: `allocate_sequence` assigns a
sequence number ONCE, on first mint, and every later call returns the stored value.
Re-deriving sequence numbers from geometry would renumber every unit after an
insertion, silently changing the identity of property people already own.
"""

from __future__ import annotations

from ..models import LedgerEntry, Unit


def allocate_sequence(conn, parent_ulpin_14: str, stratum: str, level: int, unit_id: str) -> int:
    """Return this unit's sequence number on its level, allocating it if not yet held.

    Idempotent: the same unit_id always gets the same number back.
    """
    raise NotImplementedError


def freeze(conn, unit: Unit) -> LedgerEntry:
    """Bind the provisional ULPIN to the unit permanently. Called only on approval."""
    raise NotImplementedError


def is_issued(conn, ulpin: str) -> bool:
    """True if this ULPIN has ever been issued, in any state including closed."""
    raise NotImplementedError


def mark(conn, ulpin: str, state) -> None:
    """Transition a ledger row to replaced or closed. The ULPIN is retained forever."""
    raise NotImplementedError
