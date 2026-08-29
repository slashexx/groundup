"""Load a fixture or export bundle into domain objects.

Kept separate from `store.py` because the bundle format is a transport shape, not the
persistence shape. Nothing here touches SQLite.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import (
    Accuracy,
    CreatedBy,
    DisputeState,
    ModelProvenance,
    ProjectSettings,
    Relationship,
    RelType,
    Representation,
    Status,
    Unit,
    UnitType,
    ValidationState,
)


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


def unit_from_dict(d: dict[str, Any]) -> Unit:
    m = d.get("model")
    return Unit(
        unit_id=d["unit_id"],
        unit_type=UnitType(d["unit_type"]),
        status=Status(d["status"]),
        crs=d["crs"],
        vertical_datum=d["vertical_datum"],
        footprint_2d=d["footprint_2d"],
        source_ids=list(d["source_ids"]),
        created_by=CreatedBy(d["created_by"]),
        representation=Representation(d.get("representation", "prism")),
        validation_state=ValidationState(d.get("validation_state", "unvalidated")),
        dispute_state=DisputeState(d.get("dispute_state", "undisputed")),
        ulpin=d.get("ulpin"),
        ulpin_provisional=d.get("ulpin_provisional"),
        ulpin_version=d.get("ulpin_version"),
        lower_limit=d.get("lower_limit"),
        upper_limit=d.get("upper_limit"),
        confidence_score=d.get("confidence_score"),
        model=ModelProvenance(m["name"], m["version"], _dt(m["run_at"])) if m else None,
        valid_from=_d(d.get("valid_from")),
        valid_to=_d(d.get("valid_to")),
        recorded_from=_dt(d.get("recorded_from")),
        recorded_to=_dt(d.get("recorded_to")),
        attributes=dict(d.get("attributes", {})),
    )


def accuracy_from_source(d: dict[str, Any]) -> Accuracy | None:
    """None when either component is missing - the caller must treat that as unknown,
    never as zero. A zero tolerance would flag every shared wall in the dataset.
    """
    h, v = d.get("horizontal_accuracy_m"), d.get("vertical_accuracy_m")
    return None if h is None or v is None else Accuracy(float(h), float(v))


def settings_from_dict(d: dict[str, Any]) -> ProjectSettings:
    return ProjectSettings(
        project_crs=d["project_crs"],
        vertical_datum=d["vertical_datum"],
        stratum_below_limit_m=d["stratum_below_limit_m"],
        stratum_above_limit_m=d["stratum_above_limit_m"],
        default_plinth_offset_m=d["default_plinth_offset_m"],
        default_parapet_deduction_m=d["default_parapet_deduction_m"],
        ulpin_version=d["ulpin_version"],
        ruleset_version=d["ruleset_version"],
        min_floor_height_m=d.get("min_floor_height_m", 2.4),
        max_floor_height_m=d.get("max_floor_height_m", 5.0),
        confidence_warn_below=d.get("confidence_warn_below", 0.6),
        tolerance_k=d.get("tolerance_k", 1.0),
    )


def load_bundle(path: str | Path) -> dict[str, Any]:
    """Parse a fixture/export bundle. Returns units, relationships, sources, settings."""
    raw = json.loads(Path(path).read_text())
    return {
        "settings": settings_from_dict(raw["project"]),
        "units": [unit_from_dict(u) for u in raw["units"]],
        "relationships": [
            Relationship(r["from_unit_id"], r["to_unit_id"], RelType(r["rel_type"]),
                         _dt(r["created_at"]))
            for r in raw["relationships"]
        ],
        "sources": {s["source_id"]: accuracy_from_source(s) for s in raw["sources"]},
        "raw": raw,
    }
