from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .store import get_unit, save_unit
from .ulpin import lifecycle

router = APIRouter(prefix="/cadastre", tags=["cadastre"])


class TransitionRequest(BaseModel):
    target_status: str
    actor: str
    comment: str | None = None


class ValidationRequest(BaseModel):
    db_path: str


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "block": "cadastre"}


@router.get("/units/{unit_id}")
def read_unit(unit_id: str, db_path: str = "pilot.gpkg") -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    unit = get_unit(conn, unit_id)
    conn.close()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit {unit_id} not found")
    return {
        "unit_id": unit.unit_id,
        "ulpin": unit.ulpin,
        "ulpin_provisional": unit.ulpin_provisional,
        "unit_type": unit.unit_type.value,
        "status": unit.status.value,
        "validation_state": unit.validation_state.value,
        "dispute_state": unit.dispute_state.value,
        "lower_limit": unit.lower_limit,
        "upper_limit": unit.upper_limit,
        "crs": unit.crs,
        "vertical_datum": unit.vertical_datum,
        "source_ids": unit.source_ids,
        "attributes": unit.attributes,
    }


@router.post("/units/{unit_id}/transition")
def transition_unit_status(
    unit_id: str,
    req: TransitionRequest,
    db_path: str = "pilot.gpkg",
) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    unit = get_unit(conn, unit_id)
    if not unit:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Unit {unit_id} not found")

    try:
        lifecycle.transition(
            conn=conn,
            unit=unit,
            target=req.target_status,
            actor=req.actor,
            comment=req.comment,
        )
        save_unit(conn, unit)
    except lifecycle.TransitionError as err:
        conn.close()
        raise HTTPException(status_code=400, detail=str(err))
    finally:
        conn.close()

    return {
        "unit_id": unit.unit_id,
        "status": unit.status.value,
        "ulpin": unit.ulpin,
    }

