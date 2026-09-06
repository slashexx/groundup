"""Domain objects -> the outbound contract shape.

One place where `contracts/outbound/*.schema.json` is produced, so a consumer that
generates types from the schema and a consumer that reads this output cannot drift.
The schemas set `additionalProperties: false`, so anything emitted here that is not in
the schema is a contract violation, not a harmless extra - the contracts CI job checks
exactly that.

`document()` is the whole project in one payload. P5's viewer already consumes this
shape from the committed fixture; serving the same shape live is what turns the demo
from a fixture render into a view of real data.
"""

from __future__ import annotations

from typing import Any

from .models import Finding, ProjectSettings, Relationship, Unit


def unit_to_dict(u: Unit) -> dict[str, Any]:
    """One unit, as `contracts/outbound/unit.schema.json`.

    Null-valued optional keys are omitted rather than emitted as null: the schema types
    most of them as `["string", "null"]`, so both forms validate, and omitting keeps the
    payload readable for a reviewer reading it raw.
    """
    d: dict[str, Any] = {
        "unit_id": u.unit_id,
        "unit_type": u.unit_type.value,
        "status": u.status.value,
        "validation_state": u.validation_state.value,
        "dispute_state": u.dispute_state.value,
        "representation": u.representation.value,
        "crs": u.crs,
        "vertical_datum": u.vertical_datum,
        "footprint_2d": u.footprint_2d,
        "lower_limit": u.lower_limit,
        "upper_limit": u.upper_limit,
        "source_ids": list(u.source_ids),
        "created_by": u.created_by.value,
    }
    if u.ulpin is not None:
        d["ulpin"] = u.ulpin
    if u.ulpin_provisional is not None:
        d["ulpin_provisional"] = u.ulpin_provisional
    if u.ulpin_version is not None:
        d["ulpin_version"] = u.ulpin_version
    if u.confidence_score is not None:
        d["confidence_score"] = u.confidence_score
    if u.model is not None:
        d["model"] = {"name": u.model.name, "version": u.model.version,
                      "run_at": u.model.run_at.isoformat()}
    if u.valid_from is not None:
        d["valid_from"] = u.valid_from.isoformat()
    if u.valid_to is not None:
        d["valid_to"] = u.valid_to.isoformat()
    if u.recorded_from is not None:
        d["recorded_from"] = u.recorded_from.isoformat()
    if u.recorded_to is not None:
        d["recorded_to"] = u.recorded_to.isoformat()
    if u.attributes:
        d["attributes"] = u.attributes
    return d


def finding_to_dict(f: Finding) -> dict[str, Any]:
    """One finding, as `contracts/outbound/finding.schema.json`."""
    return {
        "finding_id": f.finding_id,
        "run_id": f.run_id,
        "rule_id": f.rule_id.value,
        "severity": f.severity.value,
        "unit_id": f.unit_id,
        "related_unit_ids": list(f.related_unit_ids),
        "message": f.message,
        "suggested_action": f.suggested_action,
        "affected_geometry": f.affected_geometry,
        "measured_value": f.measured_value,
        "tolerance": f.tolerance,
        "detected_at": f.detected_at.isoformat(),
        "acknowledged_by": f.acknowledged_by,
        "acknowledged_at": f.acknowledged_at.isoformat() if f.acknowledged_at else None,
        "resolved_by": f.resolved_by,
        "resolution_note": f.resolution_note,
    }


def project_to_dict(s: ProjectSettings) -> dict[str, Any]:
    return {
        "project_crs": s.project_crs,
        "vertical_datum": s.vertical_datum,
        "stratum_below_limit_m": s.stratum_below_limit_m,
        "stratum_above_limit_m": s.stratum_above_limit_m,
        "default_plinth_offset_m": s.default_plinth_offset_m,
        "default_parapet_deduction_m": s.default_parapet_deduction_m,
        "ulpin_version": s.ulpin_version,
        "ruleset_version": s.ruleset_version,
    }


def document(
    settings: ProjectSettings,
    units: list[Unit],
    relationships: list[Relationship],
    findings: list[Finding] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The whole project in the shape `contracts/fixtures/demo-parcel.json` publishes.

    `findings` is emitted under both `findings` and `expected_findings`. The fixture
    uses the latter because in a fixture they are an expectation; live they are a
    result. Emitting both means a consumer written against the fixture keeps working
    against the endpoint without a coordinated change.

    `sources` is the provenance registry - every accuracy in this block is derived from
    it. A unit carries `source_ids` and nothing else, so a consumer holding only the
    document could show which files a unit came from but never what they are worth:
    "0.30 m, Survey of India" had to be looked up in a database the viewer cannot see.
    Emitting the registry alongside the units is what makes a displayed tolerance
    traceable rather than an assertion.
    """
    out: dict[str, Any] = {
        "project": project_to_dict(settings),
        "units": [unit_to_dict(u) for u in units],
        "relationships": [
            {"from_unit_id": r.from_unit_id, "to_unit_id": r.to_unit_id,
             "rel_type": r.rel_type.value}
            for r in relationships
        ],
        "sources": sources or [],
    }
    serialised = [finding_to_dict(f) for f in (findings or [])]
    out["findings"] = serialised
    out["expected_findings"] = serialised
    return out
