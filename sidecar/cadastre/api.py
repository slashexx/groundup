from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import validate
from .store import (
    acknowledge_finding,
    get_unit,
    load_latest_run,
    load_project,
    save_run,
    save_unit,
)
from .ulpin import encode, lifecycle

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



# --- validation results -------------------------------------------------------------
#
# Approval consults the latest persisted run. These endpoints are what put one there and
# let a reviewer act on it; without them the guard in lifecycle.transition can only ever
# refuse.


class AcknowledgeRequest(BaseModel):
    actor: str


@router.post("/validate")
def run_validation(req: ValidationRequest) -> dict[str, Any]:
    """Validate every unit in the project and persist the run."""
    conn = sqlite3.connect(req.db_path)
    conn.row_factory = sqlite3.Row
    try:
        units, rels, sources, settings = load_project(conn)
        result = validate.run(units, rels, sources, settings)
        save_run(conn, result)
        by_severity: dict[str, int] = {}
        for f in result.findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
        return {"run_id": result.run_id, "units": len(units),
                "findings": len(result.findings), "by_severity": by_severity}
    finally:
        conn.close()


@router.get("/runs/latest")
def latest_run(db_path: str = "pilot.gpkg") -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        run = load_latest_run(conn)
        if run is None:
            raise HTTPException(404, "no validation run has been recorded")
        return {"run_id": run.run_id, "ruleset_version": run.ruleset_version,
                "findings": [_finding_json(f) for f in run.findings]}
    finally:
        conn.close()


@router.post("/findings/{finding_id}/acknowledge")
def acknowledge(finding_id: str, req: AcknowledgeRequest,
                db_path: str = "pilot.gpkg") -> dict[str, Any]:
    """Record that a reviewer accepts a warning. Errors are not acknowledgeable."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        acknowledge_finding(conn, finding_id, req.actor)
        return {"finding_id": finding_id, "acknowledged_by": req.actor}
    except KeyError as err:
        raise HTTPException(404, str(err)) from err
    except ValueError as err:
        raise HTTPException(409, str(err)) from err
    finally:
        conn.close()


@router.get("/ulpin/{ulpin}")
def lookup_ulpin(ulpin: str, db_path: str = "pilot.gpkg") -> dict[str, Any]:
    """Resolve an identifier, including one that has been replaced or closed.

    A closed unit still answers - the identifier is retained forever and never reissued,
    so 'this was closed on that date' is a valid and useful answer.
    """
    if not encode.verify(ulpin):
        raise HTTPException(400, f"{ulpin} is malformed or its check character fails")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT unit_id, issued_at, ulpin_version, state FROM ulpin_ledger WHERE ulpin = ?",
            (ulpin,)).fetchone()
        if row is None:
            raise HTTPException(404, f"{ulpin} has never been issued")
        return {"ulpin": ulpin, "urn": encode.to_urn(ulpin), **dict(row),
                **encode.parse_ulpin(ulpin) | {"stratum": encode.parse_ulpin(ulpin)["stratum"].value}}
    finally:
        conn.close()


def _finding_json(f) -> dict[str, Any]:
    return {"finding_id": f.finding_id, "rule_id": f.rule_id.value,
            "severity": f.severity.value, "unit_id": f.unit_id,
            "related_unit_ids": f.related_unit_ids, "message": f.message,
            "suggested_action": f.suggested_action,
            "affected_geometry": f.affected_geometry,
            "measured_value": f.measured_value, "tolerance": f.tolerance,
            "acknowledged_by": f.acknowledged_by}
