"""ULPIN allocation and the non-reuse guarantee (FR-06).

The ledger is the reason an issued ULPIN can never be handed to another unit, even
after the original is closed. Rows are appended, never deleted.

It is also where the determinism trap is defused: `allocate_sequence` assigns a
sequence number ONCE, on first mint, and every later call returns the stored value.
Re-deriving sequence numbers from geometry would renumber every unit after an
insertion, silently changing the identity of property people already own.
"""

import sqlite3
from datetime import UTC, datetime

from ..models import LedgerEntry, LedgerState, Status, Unit
from .encode import Stratum, format_ulpin


def allocate_sequence(
    conn: sqlite3.Connection, parent_ulpin_14: str, stratum: str, level: int, unit_id: str
) -> int:
    """Return this unit's sequence number on its level, allocating it if not yet held.

    Idempotent: the same unit_id always gets the same number back.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT sequence FROM ulpin_sequence WHERE parent_ulpin_14 = ? AND stratum = ? AND level = ? AND unit_id = ?",
        (parent_ulpin_14, stratum, level, unit_id),
    )
    row = cur.fetchone()
    if row is not None:
        return int(row[0])

    cur.execute(
        "SELECT COALESCE(MAX(sequence), -1) + 1 FROM ulpin_sequence WHERE parent_ulpin_14 = ? AND stratum = ? AND level = ?",
        (parent_ulpin_14, stratum, level),
    )
    next_seq = int(cur.fetchone()[0])

    cur.execute(
        "INSERT INTO ulpin_sequence (parent_ulpin_14, stratum, level, unit_id, sequence) VALUES (?, ?, ?, ?, ?)",
        (parent_ulpin_14, stratum, level, unit_id, next_seq),
    )
    conn.commit()
    return next_seq


def freeze(conn: sqlite3.Connection, unit: Unit, parent_ulpin_14: str | None = None, version: int = 1) -> LedgerEntry:
    """Bind the provisional ULPIN to the unit permanently. Called only on approval."""
    ulpin_str = unit.ulpin_provisional
    if not ulpin_str:
        if parent_ulpin_14 is None:
            parent_ulpin_14 = unit.attributes.get("parent_ulpin_14", "KA05B012345678")
        floor_idx = unit.attributes.get("floor_index", 0)
        if floor_idx < 0:
            stratum = Stratum.BELOW
        elif floor_idx == 0 and unit.unit_type.value == "land_parcel":
            stratum = Stratum.SURFACE
        else:
            stratum = Stratum.ABOVE
        level = abs(floor_idx)
        seq = allocate_sequence(conn, parent_ulpin_14, stratum.value, level, unit.unit_id)
        ulpin_str = format_ulpin(parent_ulpin_14, version, stratum, level, seq)

    now = datetime.now(UTC)
    version_str = unit.ulpin_version or f"v{version}"
    entry = LedgerEntry(
        ulpin=ulpin_str,
        unit_id=unit.unit_id,
        issued_at=now,
        ulpin_version=version_str,
        state=LedgerState.ISSUED,
    )
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ulpin_ledger (ulpin, unit_id, issued_at, ulpin_version, state) VALUES (?, ?, ?, ?, ?)",
        (entry.ulpin, entry.unit_id, entry.issued_at.isoformat(), entry.ulpin_version, entry.state.value),
    )
    cur.execute(
        "UPDATE unit SET ulpin = ?, ulpin_provisional = NULL, status = ? WHERE unit_id = ?",
        (entry.ulpin, Status.APPROVED.value, unit.unit_id),
    )
    conn.commit()
    unit.ulpin = entry.ulpin
    unit.ulpin_provisional = None
    unit.status = Status.APPROVED
    return entry


def is_issued(conn: sqlite3.Connection, ulpin: str) -> bool:
    """True if this ULPIN has ever been issued, in any state including closed."""
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM ulpin_ledger WHERE ulpin = ?", (ulpin,))
    return cur.fetchone() is not None


def mark(conn: sqlite3.Connection, ulpin: str, state: LedgerState | str) -> None:
    """Transition a ledger row to replaced or closed. The ULPIN is retained forever."""
    state_val = state.value if isinstance(state, LedgerState) else str(state)
    cur = conn.cursor()
    cur.execute("UPDATE ulpin_ledger SET state = ? WHERE ulpin = ?", (state_val, ulpin))
    conn.commit()

