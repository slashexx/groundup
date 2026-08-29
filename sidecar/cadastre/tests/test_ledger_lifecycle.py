"""Tests for ULPIN ledger, sequence allocation, lifecycle state transitions, and store CRUD."""

from __future__ import annotations

import sqlite3

import pytest
from cadastre.models import CreatedBy, Representation, Status, Unit, UnitType
from cadastre.store import get_unit, init_schema, save_unit
from cadastre.ulpin import ledger, lifecycle


@pytest.fixture
def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


def _sample_unit(uid="UNIT-001", status=Status.DRAFT) -> Unit:
    return Unit(
        unit_id=uid,
        unit_type=UnitType.APARTMENT,
        status=status,
        crs="EPSG:32643",
        vertical_datum="EGM2008",
        footprint_2d={
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        },
        source_ids=["SRC-001"],
        created_by=CreatedBy.HUMAN,
        representation=Representation.PRISM,
        lower_limit=918.5,
        upper_limit=921.5,
        attributes={"parent_ulpin_14": "KA05B012345678", "floor_index": 1},
    )


def test_sequence_allocation_is_idempotent(memory_db):
    seq1 = ledger.allocate_sequence(memory_db, "KA05B012345678", "A", 1, "UNIT-001")
    seq2 = ledger.allocate_sequence(memory_db, "KA05B012345678", "A", 1, "UNIT-001")
    assert seq1 == seq2

    # Second unit gets the next sequence
    seq3 = ledger.allocate_sequence(memory_db, "KA05B012345678", "A", 1, "UNIT-002")
    assert seq3 == seq1 + 1


def test_lifecycle_transitions(memory_db):
    u = _sample_unit("UNIT-100", status=Status.DRAFT)
    save_unit(memory_db, u)

    # DRAFT -> PROCESSING
    lifecycle.transition(memory_db, u, Status.PROCESSING, actor="operator")
    assert u.status == Status.PROCESSING

    # PROCESSING -> NEEDS_REVIEW
    lifecycle.transition(memory_db, u, Status.NEEDS_REVIEW, actor="operator")
    assert u.status == Status.NEEDS_REVIEW

    # NEEDS_REVIEW -> APPROVED (triggers ledger freeze)
    lifecycle.transition(memory_db, u, Status.APPROVED, actor="reviewer")
    assert u.status == Status.APPROVED
    assert u.ulpin is not None
    assert ledger.is_issued(memory_db, u.ulpin)

    # Invalid transition APPROVED -> DRAFT must raise TransitionError
    with pytest.raises(lifecycle.TransitionError):
        lifecycle.transition(memory_db, u, Status.DRAFT, actor="hacker")


def test_store_save_and_get_unit(memory_db):
    u = _sample_unit("UNIT-200")
    save_unit(memory_db, u)

    retrieved = get_unit(memory_db, "UNIT-200")
    assert retrieved is not None
    assert retrieved.unit_id == "UNIT-200"
    assert retrieved.status == Status.DRAFT
    assert retrieved.lower_limit == 918.5
    assert retrieved.attributes == {"parent_ulpin_14": "KA05B012345678", "floor_index": 1}
