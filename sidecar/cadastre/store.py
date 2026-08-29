"""Persistence. Five tables, all inside the project .gpkg.

A GeoPackage is just SQLite, so our registry tables live alongside the spatial layers
in the same single portable file. Spatial layers are read with geopandas; these tables
are plain sqlite3.
"""

from __future__ import annotations

import sqlite3

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
