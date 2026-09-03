from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import derive, export, ingest_gpkg, store, validate
from .store import (
    ProjectIncomplete,
    acknowledge_finding,
    get_unit,
    init_schema,
    load_latest_run,
    load_project,
    save_run,
    save_unit,
)
from .ulpin import encode, ledger, lifecycle

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
        raise HTTPException(status_code=400, detail=str(err)) from err
    except (ledger.UnknownParcel, ledger.AlreadyIssued) as err:
        # A guard that fires correctly still owes the caller a readable answer.
        conn.close()
        raise HTTPException(status_code=409, detail=str(err)) from err
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
        save_run(conn, result, [u.unit_id for u in units])
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
    return export.finding_to_dict(f)


# --- integration surface ------------------------------------------------------------
#
# Two routes the rest of the team consumes: one that turns P2's harmonized GeoPackage
# into units, and one that hands P5 and P6 the whole project in the outbound contract
# shape. Together they are the difference between a block that passes its own tests and
# a block the other five can actually reach.


@router.post("/ingest")
def ingest_geopackage(req: ValidationRequest) -> dict[str, Any]:
    """Import P2's `parcel`, `building_footprint` and `utility_line` layers.

    Repeatable: a unit already imported keeps the `unit_id` it was allocated, so running
    this again after P2 adds a layer does not mint a second identity for the same parcel.
    """
    conn = sqlite3.connect(req.db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        settings = load_project(conn)[3]
        report = ingest_gpkg.import_project(conn, settings)
        return {
            "units": len(report.units),
            "created": report.created,
            "reused": report.reused,
            "relationships": len(report.relationships),
            "provisional_ulpins": report.minted,
            "unresolved_buildings": report.unresolved,
        }
    except (ingest_gpkg.LayerMissing, ProjectIncomplete) as err:
        raise HTTPException(422, str(err)) from err
    finally:
        conn.close()


@router.get("/document")
def project_document(db_path: str = "pilot.gpkg") -> dict[str, Any]:
    """The whole project in the outbound contract shape, findings included.

    This is what P5's `fromP4Document()` already knows how to read, so pointing the
    viewer at this URL replaces the committed fixture with live data and nothing else
    has to change.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        units, rels, _sources, settings = load_project(conn)
        run = load_latest_run(conn)
        return export.document(settings, units, rels, run.findings if run else [])
    except ProjectIncomplete as err:
        raise HTTPException(422, str(err)) from err
    finally:
        conn.close()


@router.post("/derive")
def derive_from_rasters(req: ValidationRequest) -> dict[str, Any]:
    """Give imported buildings a height range and a floor stack from registered rasters.

    The seam between ingest, which imports footprints with no heights because P2
    registers rasters but does not deliver elevation through the GeoPackage, and extrude,
    which can derive heights but does not know where a project's rasters live. Without
    this step the chain stops at footprints: no heights, no floors, nothing approvable.

    A building no registered raster covers is left exactly as ingest produced it and
    surfaces as HEIGHTS_UNAVAILABLE at validation - visible in the review queue rather
    than silently absent.
    """
    conn = sqlite3.connect(req.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return derive.derive_heights(conn).as_dict()
    except store.ProjectIncomplete as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    finally:
        conn.close()
