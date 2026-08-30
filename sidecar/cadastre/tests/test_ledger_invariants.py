"""Adversarial tests for the two ULPIN invariants.

These are the rules the register rests on, so they are tested by attacking them rather
than by exercising the happy path:

  * a sequence number, once issued, is never handed to a different unit
  * a unit is never minted under a parcel nobody chose
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cadastre import store
from cadastre.models import CreatedBy, Status, Unit, UnitType
from cadastre.ulpin import encode, ledger

PARENT = "KA05B012345678"
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    store.init_schema(c)
    return c


def unit(uid: str, provisional: str | None = None, parent: str | None = PARENT) -> Unit:
    attrs = {"floor_index": 1}
    if parent is not None:
        attrs["parent_ulpin_14"] = parent
    return Unit(
        unit_id=uid, unit_type=UnitType.APARTMENT, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008", footprint_2d=SQUARE,
        source_ids=["SRC-005"], created_by=CreatedBy.HUMAN,
        ulpin_provisional=provisional, ulpin_version="v1",
        recorded_from=datetime.now(timezone.utc), attributes=attrs,
    )


def test_sequence_allocation_is_idempotent(conn):
    a = ledger.allocate_sequence(conn, PARENT, "A", 1, "U-A")
    ledger.allocate_sequence(conn, PARENT, "A", 1, "U-B")
    assert ledger.allocate_sequence(conn, PARENT, "A", 1, "U-A") == a


def test_a_later_unit_never_renumbers_an_earlier_one(conn):
    """The determinism trap. Re-deriving sequence numbers from position would change
    the identity of property somebody already owns.
    """
    first = ledger.allocate_sequence(conn, PARENT, "A", 1, "U-FIRST")
    for i in range(5):
        ledger.allocate_sequence(conn, PARENT, "A", 1, f"U-LATER-{i}")
    assert ledger.allocate_sequence(conn, PARENT, "A", 1, "U-FIRST") == first


def test_freezing_a_provisional_id_reserves_its_sequence(conn):
    """A unit that arrives with a provisional ULPIN still consumes that sequence number.

    Without this, the sequence table never learns the number is taken, allocation
    eventually reaches it, and a legitimate approval dies on a primary-key violation
    naming a database constraint rather than the actual problem.
    """
    early = unit("U-EARLY", provisional=encode.format_ulpin(PARENT, 1, encode.Stratum.ABOVE, 1, 3))
    ledger.freeze(conn, early)

    taken = {r[0] for r in conn.execute("SELECT sequence FROM ulpin_sequence")}
    assert 3 in taken, "the provisional's sequence was never reserved"

    for i in range(6):
        ledger.freeze(conn, unit(f"U-{i}"))          # must not raise
    issued = [r[0] for r in conn.execute("SELECT ulpin FROM ulpin_ledger")]
    assert len(issued) == len(set(issued)) == 7


def test_an_issued_ulpin_is_never_reused(conn):
    first = unit("U-1")
    ledger.freeze(conn, first)
    assert ledger.is_issued(conn, first.ulpin)

    ledger.mark(conn, first.ulpin, "closed")
    assert ledger.is_issued(conn, first.ulpin), "closing must not release the identifier"

    second = unit("U-2")
    ledger.freeze(conn, second)
    assert second.ulpin != first.ulpin


def test_minting_without_a_parcel_is_refused(conn):
    """A unit with no parent must never be quietly minted under some other parcel.

    Assigning a real property to the wrong land is the single worst output this module
    can produce, and it would look entirely well-formed.
    """
    with pytest.raises(ledger.UnknownParcel):
        ledger.freeze(conn, unit("U-ORPHAN", parent=None))


def test_freezing_a_taken_identifier_reports_the_cause(conn):
    ledger.freeze(conn, unit("U-1", provisional=encode.format_ulpin(
        PARENT, 1, encode.Stratum.ABOVE, 1, 9)))
    clash = unit("U-2", provisional=encode.format_ulpin(PARENT, 1, encode.Stratum.ABOVE, 1, 9))
    with pytest.raises(ledger.AlreadyIssued, match="already issued"):
        ledger.freeze(conn, clash)
