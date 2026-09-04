import json
import sqlite3
from datetime import UTC, date, datetime

import shapely.geometry
import shapely.wkb

from .models import (
    Accuracy,
    CreatedBy,
    DisputeState,
    Finding,
    ModelProvenance,
    Relationship,
    RelType,
    Representation,
    RuleId,
    Severity,
    Status,
    Unit,
    UnitType,
    ValidationState,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS unit (
    unit_id            TEXT PRIMARY KEY,
    ulpin              TEXT UNIQUE,
    ulpin_provisional  TEXT,
    ulpin_version      TEXT,
    unit_type          TEXT NOT NULL,
    status             TEXT NOT NULL,
    validation_state   TEXT NOT NULL DEFAULT 'unvalidated',
    dispute_state      TEXT NOT NULL DEFAULT 'undisputed',
    representation     TEXT NOT NULL DEFAULT 'prism',
    crs                TEXT NOT NULL,
    vertical_datum     TEXT NOT NULL,
    footprint_wkb      BLOB NOT NULL,
    lower_limit        REAL,
    upper_limit        REAL,
    source_ids         TEXT NOT NULL,
    created_by         TEXT NOT NULL,
    confidence_score   REAL,
    model_name         TEXT,
    model_version      TEXT,
    model_run_at       TEXT,
    valid_from         TEXT,
    valid_to           TEXT,
    recorded_from      TEXT NOT NULL,
    recorded_to        TEXT,
    attributes         TEXT NOT NULL DEFAULT '{}',
    CHECK (status <> 'approved' OR ulpin IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS unit_relationship (
    from_unit_id TEXT NOT NULL REFERENCES unit(unit_id),
    to_unit_id   TEXT NOT NULL REFERENCES unit(unit_id),
    rel_type     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (from_unit_id, to_unit_id, rel_type)
);

-- Append-only. This is how FR-06's non-reuse guarantee is proven.
CREATE TABLE IF NOT EXISTS ulpin_ledger (
    ulpin         TEXT PRIMARY KEY,
    unit_id       TEXT NOT NULL,
    issued_at     TEXT NOT NULL,
    ulpin_version TEXT NOT NULL,
    state         TEXT NOT NULL
);

-- Sequence numbers are allocated once and never re-derived. See ulpin/ledger.py.
CREATE TABLE IF NOT EXISTS ulpin_sequence (
    parent_ulpin_14 TEXT NOT NULL,
    stratum         TEXT NOT NULL,
    level           INTEGER NOT NULL,
    unit_id         TEXT NOT NULL,
    sequence        INTEGER NOT NULL,
    PRIMARY KEY (parent_ulpin_14, stratum, level, unit_id)
);

CREATE TABLE IF NOT EXISTS validation_run (
    run_id           TEXT PRIMARY KEY,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    ruleset_version  TEXT NOT NULL,
    scope            TEXT
);

CREATE TABLE IF NOT EXISTS finding (
    finding_id        TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES validation_run(run_id),
    rule_id           TEXT NOT NULL,
    severity          TEXT NOT NULL,
    unit_id           TEXT NOT NULL,
    related_unit_ids  TEXT NOT NULL DEFAULT '[]',
    message           TEXT NOT NULL,
    suggested_action  TEXT,
    affected_geometry TEXT,
    measured_value    REAL,
    tolerance         REAL,
    detected_at       TEXT NOT NULL,
    acknowledged_by   TEXT,
    acknowledged_at   TEXT,
    resolved_by       TEXT,
    resolution_note   TEXT
);

-- What P3 handed us, and what a human decided about it. Kept as a table of its own
-- rather than as provisional units, because a suggestion is not a unit: it has no
-- identity to protect, it may be rejected outright, and the record of *who decided* is
-- the evidence that FR-05 was honoured. A unit appears only once someone accepts one.
CREATE TABLE IF NOT EXISTS ai_suggestion (
    suggestion_id     TEXT PRIMARY KEY,
    kind              TEXT NOT NULL,
    geometry          TEXT NOT NULL,      -- GeoJSON Polygon in the project CRS, not WGS84
    crs               TEXT NOT NULL,
    source_raster_ids TEXT NOT NULL,
    confidence        REAL NOT NULL,
    model_name        TEXT NOT NULL,
    model_version     TEXT NOT NULL,
    model_run_at      TEXT NOT NULL,
    attributes        TEXT NOT NULL DEFAULT '{}',
    review_state      TEXT NOT NULL,
    reviewed_by       TEXT,
    reviewed_at       TEXT,
    edited_geometry   TEXT,
    unit_id           TEXT,               -- the unit it became, once applied
    received_at       TEXT NOT NULL,
    CHECK (review_state IN ('pending', 'accepted', 'edited', 'rejected')),
    -- The contract says P4 uses `edited_geometry` and not `geometry` when the state is
    -- `edited`. Enforced here so an edited suggestion can never silently fall back to
    -- the outline the model drew - the reviewer's correction would be lost in exactly
    -- the case where it matters most.
    CHECK (review_state <> 'edited' OR edited_geometry IS NOT NULL),
    -- A decision has an author. `pending` is the only state nobody signed.
    CHECK (review_state = 'pending' OR reviewed_by IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_unit_status  ON unit(status);
CREATE INDEX IF NOT EXISTS idx_unit_type    ON unit(unit_type);
CREATE INDEX IF NOT EXISTS idx_finding_unit ON finding(unit_id);
CREATE INDEX IF NOT EXISTS idx_finding_run  ON finding(run_id);
"""


def connect(gpkg_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(gpkg_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def save_unit(conn: sqlite3.Connection, unit: Unit) -> None:
    """Save or update a Unit in the SQLite database."""
    wkb = shapely.geometry.shape(unit.footprint_2d).wkb
    rec_from = unit.recorded_from.isoformat() if unit.recorded_from else datetime.now(UTC).isoformat()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO unit (
            unit_id, ulpin, ulpin_provisional, ulpin_version, unit_type, status,
            validation_state, dispute_state, representation, crs, vertical_datum,
            footprint_wkb, lower_limit, upper_limit, source_ids, created_by,
            confidence_score, model_name, model_version, model_run_at, valid_from,
            valid_to, recorded_from, recorded_to, attributes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            unit.unit_id,
            unit.ulpin,
            unit.ulpin_provisional,
            unit.ulpin_version,
            unit.unit_type.value if hasattr(unit.unit_type, 'value') else str(unit.unit_type),
            unit.status.value if hasattr(unit.status, 'value') else str(unit.status),
            unit.validation_state.value if hasattr(unit.validation_state, 'value') else str(unit.validation_state),
            unit.dispute_state.value if hasattr(unit.dispute_state, 'value') else str(unit.dispute_state),
            unit.representation.value if hasattr(unit.representation, 'value') else str(unit.representation),
            unit.crs,
            unit.vertical_datum,
            wkb,
            unit.lower_limit,
            unit.upper_limit,
            json.dumps(unit.source_ids),
            unit.created_by.value if hasattr(unit.created_by, 'value') else str(unit.created_by),
            unit.confidence_score,
            unit.model.name if unit.model else None,
            unit.model.version if unit.model else None,
            unit.model.run_at.isoformat() if unit.model and unit.model.run_at else None,
            unit.valid_from.isoformat() if unit.valid_from else None,
            unit.valid_to.isoformat() if unit.valid_to else None,
            rec_from,
            unit.recorded_to.isoformat() if unit.recorded_to else None,
            json.dumps(unit.attributes),
        ),
    )
    conn.commit()


def get_unit(conn: sqlite3.Connection, unit_id: str) -> Unit | None:
    """Retrieve a Unit by ID from the SQLite database."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM unit WHERE unit_id = ?", (unit_id,))
    row = cur.fetchone()
    if not row:
        return None

    geom = shapely.wkb.loads(row["footprint_wkb"])
    footprint_2d = shapely.geometry.mapping(geom)

    m_name, m_ver, m_run = row["model_name"], row["model_version"], row["model_run_at"]
    model = (
        ModelProvenance(m_name, m_ver, datetime.fromisoformat(m_run))
        if m_name and m_ver and m_run
        else None
    )

    return Unit(
        unit_id=row["unit_id"],
        unit_type=UnitType(row["unit_type"]),
        status=Status(row["status"]),
        crs=row["crs"],
        vertical_datum=row["vertical_datum"],
        footprint_2d=footprint_2d,
        source_ids=json.loads(row["source_ids"]),
        created_by=CreatedBy(row["created_by"]),
        representation=Representation(row["representation"]),
        validation_state=ValidationState(row["validation_state"]),
        dispute_state=DisputeState(row["dispute_state"]),
        ulpin=row["ulpin"],
        ulpin_provisional=row["ulpin_provisional"],
        ulpin_version=row["ulpin_version"],
        lower_limit=row["lower_limit"],
        upper_limit=row["upper_limit"],
        confidence_score=row["confidence_score"],
        model=model,
        valid_from=date.fromisoformat(row["valid_from"]) if row["valid_from"] else None,
        valid_to=date.fromisoformat(row["valid_to"]) if row["valid_to"] else None,
        recorded_from=datetime.fromisoformat(row["recorded_from"]) if row["recorded_from"] else None,
        recorded_to=datetime.fromisoformat(row["recorded_to"]) if row["recorded_to"] else None,
        attributes=json.loads(row["attributes"]) if row["attributes"] else {},
    )


def save_relationship(conn: sqlite3.Connection, rel: Relationship) -> None:
    """Save a Relationship between units."""
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO unit_relationship (from_unit_id, to_unit_id, rel_type, created_at) VALUES (?, ?, ?, ?)",
        (rel.from_unit_id, rel.to_unit_id, rel.rel_type.value, rel.created_at.isoformat()),
    )
    conn.commit()



# --- validation results -------------------------------------------------------------
#
# The `finding` and `validation_run` tables were defined from the start but nothing wrote
# to them, so validation was computed in memory and discarded. That left the approval
# guard with nothing to consult and no reviewer able to acknowledge a warning.


class ProjectIncomplete(RuntimeError):
    """The GeoPackage is missing tables the ingest block is responsible for writing."""


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def save_run(conn: sqlite3.Connection, run, validated_unit_ids: list[str] | None = None) -> None:
    """Persist a validation run, every finding it produced, and the resulting states.

    Writing `unit.validation_state` back is not bookkeeping. The column is part of the
    outbound contract and is what a reviewer sorts by and what P5 colours the map by;
    leaving it at its `unvalidated` default after a run that found three errors makes
    every consumer show a project that has never been checked.

    `validated_unit_ids` names what the run actually covered. Without it the run is
    taken to be project-wide - which is what `validate.run` does today - and a unit with
    no findings is genuinely passed. A scoped run must pass its own ids, because marking
    a unit passed on the strength of a run that never looked at it is the same class of
    error as approving one with no run at all.
    """
    conn.execute(
        "INSERT OR REPLACE INTO validation_run "
        "(run_id, started_at, finished_at, ruleset_version, scope) VALUES (?,?,?,?,?)",
        (run.run_id, _iso(run.started_at), _iso(run.finished_at),
         run.ruleset_version, getattr(run, "scope", None)),
    )
    conn.executemany(
        "INSERT OR REPLACE INTO finding (finding_id, run_id, rule_id, severity, unit_id, "
        "related_unit_ids, message, suggested_action, affected_geometry, measured_value, "
        "tolerance, detected_at, acknowledged_by, acknowledged_at, resolved_by, "
        "resolution_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(f.finding_id, f.run_id, f.rule_id.value, f.severity.value, f.unit_id,
          json.dumps(f.related_unit_ids), f.message, f.suggested_action,
          json.dumps(f.affected_geometry) if f.affected_geometry else None,
          f.measured_value, f.tolerance, _iso(f.detected_at), f.acknowledged_by,
          _iso(f.acknowledged_at), f.resolved_by, f.resolution_note)
         for f in run.findings],
    )

    covered = (
        validated_unit_ids
        if validated_unit_ids is not None
        else [r["unit_id"] for r in conn.execute("SELECT unit_id FROM unit")]
    )
    conn.executemany(
        "UPDATE unit SET validation_state = ? WHERE unit_id = ?",
        [(run.state_of(uid).value, uid) for uid in covered],
    )
    conn.commit()


def _finding_from_row(r: sqlite3.Row) -> Finding:
    return Finding(
        finding_id=r["finding_id"], run_id=r["run_id"], rule_id=RuleId(r["rule_id"]),
        severity=Severity(r["severity"]), unit_id=r["unit_id"], message=r["message"],
        detected_at=_dt(r["detected_at"]),
        related_unit_ids=json.loads(r["related_unit_ids"] or "[]"),
        suggested_action=r["suggested_action"],
        affected_geometry=json.loads(r["affected_geometry"]) if r["affected_geometry"] else None,
        measured_value=r["measured_value"], tolerance=r["tolerance"],
        acknowledged_by=r["acknowledged_by"], acknowledged_at=_dt(r["acknowledged_at"]),
        resolved_by=r["resolved_by"], resolution_note=r["resolution_note"],
    )


def get_findings(conn: sqlite3.Connection, run_id: str) -> list[Finding]:
    rows = conn.execute("SELECT * FROM finding WHERE run_id = ?", (run_id,)).fetchall()
    return [_finding_from_row(r) for r in rows]


def load_latest_run(conn: sqlite3.Connection):
    """The most recent validation run, or None if validation has never been recorded.

    None means "we cannot verify this unit", and callers must treat it as a refusal
    rather than as an absence of problems.
    """
    from .validate.engine import ValidationRun

    row = conn.execute(
        "SELECT * FROM validation_run ORDER BY started_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return ValidationRun(
        run_id=row["run_id"], started_at=_dt(row["started_at"]),
        finished_at=_dt(row["finished_at"]), ruleset_version=row["ruleset_version"],
        findings=get_findings(conn, row["run_id"]),
    )


def acknowledge_finding(conn: sqlite3.Connection, finding_id: str, actor: str) -> None:
    """Record that a reviewer has seen a warning and accepts it.

    Only warnings are acknowledgeable. An error is not something a reviewer may wave
    through - it must be fixed and validation re-run.
    """
    row = conn.execute("SELECT severity FROM finding WHERE finding_id = ?",
                       (finding_id,)).fetchone()
    if row is None:
        raise KeyError(f"no finding {finding_id}")
    if row["severity"] == Severity.ERROR.value:
        raise ValueError(
            f"{finding_id} is an error, which cannot be acknowledged. Correct the unit "
            "and re-run validation.")
    conn.execute(
        "UPDATE finding SET acknowledged_by = ?, acknowledged_at = ? WHERE finding_id = ?",
        (actor, _iso(datetime.now(UTC)), finding_id),
    )
    conn.commit()


def load_project(conn: sqlite3.Connection):
    """Read a whole project back for validation: units, relationships, sources, settings.

    `source` and `project_settings` are written by the ingest block, not by us. Their
    absence is a real condition - an empty or partially built GeoPackage - and is
    reported rather than papered over with defaults, because a made-up project CRS or a
    made-up accuracy would silently change every result.
    """
    from .loader import settings_from_dict

    # Our own tables, guarded exactly like P2's below. `sqlite3.connect` creates an empty
    # file for a path that does not exist, so a mistyped `db_path` reaches here as a
    # blank database rather than as an error - and an unguarded read then leaves the API
    # answering 500 with a stack trace where it means "this is not a project yet". A
    # guard that fires correctly still owes the caller a readable answer.
    try:
        unit_ids = [r["unit_id"] for r in conn.execute("SELECT unit_id FROM unit")]
        rels = [
            Relationship(r["from_unit_id"], r["to_unit_id"], RelType(r["rel_type"]),
                         _dt(r["created_at"]))
            for r in conn.execute("SELECT * FROM unit_relationship")
        ]
    except sqlite3.OperationalError as err:
        raise ProjectIncomplete(
            "no `unit` table - this GeoPackage has never been through `init_schema`, so "
            "it is either not a project or the ingest step has not run. Check the path, "
            "then POST /cadastre/ingest.") from err
    units = [u for u in (get_unit(conn, uid) for uid in unit_ids) if u is not None]

    try:
        rows = conn.execute(
            "SELECT source_id, horizontal_accuracy_m, vertical_accuracy_m FROM source"
        ).fetchall()
    except sqlite3.OperationalError as err:
        raise ProjectIncomplete(
            "no `source` table - the ingest block has not written the source registry. "
            "Validation tolerances are derived from it and cannot be guessed.") from err
    sources = {
        r["source_id"]: (
            Accuracy(r["horizontal_accuracy_m"], r["vertical_accuracy_m"])
            if r["horizontal_accuracy_m"] is not None
            and r["vertical_accuracy_m"] is not None else None
        )
        for r in rows
    }

    try:
        row = conn.execute("SELECT * FROM project_settings LIMIT 1").fetchone()
    except sqlite3.OperationalError as err:
        raise ProjectIncomplete("no `project_settings` table") from err
    if row is None:
        raise ProjectIncomplete("`project_settings` is empty")

    return units, rels, sources, settings_from_dict(dict(row))
