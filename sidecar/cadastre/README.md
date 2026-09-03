# Cadastre Block (`sidecar/cadastre`)

**System:** 3D ULPIN Generation and Vertical Property Mapping System (SIH26011)  
**Owners:** **dhruv** (rasters, geometry & spatial predicates) · **shankhanil** (identity, process, ledger & schema)  
**Package:** `sidecar/cadastre/`  

The `cadastre` block turns flat shapes into **owned 3D volumes with permanent identities**, and proves those volumes are mutually consistent. Everything upstream (P2 ingest, P3 AI) produces raw geometry and loose numbers; everything downstream (P5 viewer, P6 export) displays and publishes. This module makes the system a **cadastre** rather than a 3D model viewer.

---

## 1. Quick Start

### Environment & Tests

```bash
# Setup virtual environment and install dependencies
python3 -m venv .venv
./.venv/bin/pip install shapely pytest hypothesis jsonschema rasterio numpy fastapi pydantic uvicorn ruff

# Run the automated test suite
./.venv/bin/python -m pytest sidecar/cadastre/tests -q

# Every guard must be load-bearing: each mutation removes one and must turn the suite red
./.venv/bin/python sidecar/cadastre/tools/mutation_check.py

# Run code linter
./.venv/bin/ruff check sidecar/cadastre

# Regenerate demo fixture
./.venv/bin/python sidecar/cadastre/tools/make_fixture.py
```

### Local sidecar API

```bash
./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --reload --port 8000
```

> **Run `cadastre.app:app`, not `cadastre.api:router`.** `api.router` is an `APIRouter`,
> not an application. Uvicorn starts happily with it as a target — it is technically an
> ASGI callable — and then answers **500 on every route**. This README said `:router` for
> a while and that command never served a single request.

Then, against a GeoPackage the ingest block has written:

```bash
curl -X POST localhost:8000/cadastre/ingest   -H 'content-type: application/json' -d '{"db_path":"pilot.gpkg"}'
curl -X POST localhost:8000/cadastre/validate -H 'content-type: application/json' -d '{"db_path":"pilot.gpkg"}'
curl "localhost:8000/cadastre/document?db_path=pilot.gpkg"
```

`/cadastre/document` returns the whole project in the same shape as
`contracts/fixtures/demo-parcel.json`, which is what the viewer and the desktop shell
consume. Interactive docs at <http://localhost:8000/docs>.

---

## 2. Core Architecture & Concepts

### 2.1 3D ULPIN Format (Extending Bhu-Aadhaar)
The 14-character parent 2D ULPIN (`KA05B012345678`) is preserved untouched. P4 appends stratum, level, unit sequence, and an **ISO 7064 MOD 37,36 check character**:

```
KA05B012345678 - V1 - A07 - 003 - K      urn:ulpin:3d:v1:KA05B012345678:A:07:003
└─────┬──────┘   └┬┘  └┬┘   └┬┘   └┬┘
 14-char parent   │    │     │     └ ISO 7064 MOD 37,36 check character (catches 100% substitutions)
 (untouched)      │    │     └ unit sequence on level (003 = 3rd unit)
                  │    └ stratum (A=above, S=surface, B=below) + 2-digit level
                  └ scheme version
```

### 2.2 Sequence Locking & Append-Only Ledger
* **Identity vs. Locator Split:** `unit_id` is an opaque UUID allocated once. Sequence numbers are assigned **once** via `ulpin_sequence` and locked forever. Spatially re-deriving sequence numbers after an insertion is prohibited.
* **Approval & Ledger Freeze:** On approval, the provisional ULPIN is stamped, updated in SQLite, and appended to `ulpin_ledger`. Approved records are immutable.

### 2.3 Prism Decomposition & Validation
* **No 3D Boolean Engine Needed:** Two units intersect $\iff$ 2D footprints intersect AND Z-intervals overlap.
* **Type-Conditional Containment:** Ownership units (apartments, buildings) must fit inside their parent land parcel. **Easements** (underground water mains, metro tunnels, elevated walkways) are expected to cross parcel boundaries.
* **Provenance-Derived Tolerances:** Comparison tolerances are calculated dynamically from source data accuracy ($k \cdot \sqrt{\text{acc}_A^2 + \text{acc}_B^2}$). Overlaps smaller than measurement noise are ignored to avoid reviewer fatigue.

---

## 3. Directory Layout & Module Structure

```
sidecar/cadastre/
├── models.py             Domain dataclasses (Unit, Finding, Relationship, LedgerEntry)
├── store.py              6-table GeoPackage SQLite persistence layer & CRUD helpers
├── loader.py             Import transport JSON bundles into domain objects
├── api.py                FastAPI router endpoints for local sidecar integration
│
├── extrude/              [Dhruv] Shape & raster processing
│   ├── raster.py         Median zonal statistics over DEM/DSM rasters
│   ├── building.py       Footprint + median elevations -> building Z-limits
│   ├── floors.py         Building height -> N floor units
│   └── subdivide.py      Floor -> apartment polygon subdivisions
│
├── ulpin/                [Shankhanil] Identity, ledger & lifecycle
│   ├── encode.py         Format ULPINs, parse URNs, ISO 7064 check character
│   ├── ledger.py         Sequence allocation, ULPIN freezing, append-only log
│   └── lifecycle.py      State machine (Draft -> Processing -> Review -> Approved)
│
├── validate/             [Dhruv & Shankhanil] Validation engine
│   ├── engine.py         Rule orchestrator & validation run manager
│   ├── context.py        Shapely STRtree spatial index & accuracy graph
│   ├── tolerance.py      Source accuracy -> tolerance calculation
│   └── rules/            Rule modules (geometry, overlap, containment, sequence, metadata)
│
├── tools/
│   ├── make_fixture.py   Generator for contracts/fixtures/demo-parcel.json
│   └── make_rasters.py   Synthetic DEM/DSM raster generator for tests
│
└── tests/                Pytest suite (37 unit & property-based tests)
```

---

## 4. API & Schema Report

### 4.1 REST API Endpoints ([`api.py`](./api.py))

#### `GET /cadastre/health`
Health check endpoint.

* **Response (200 OK):**
```json
{
  "status": "ok",
  "block": "cadastre"
}
```

#### `GET /cadastre/units/{unit_id}`
Fetch unit by `unit_id` from the SQLite GeoPackage store.

* **Response (200 OK):**
```json
{
  "unit_id": "APT-101",
  "ulpin": "KA05B012345678-V1-A01-001-K",
  "ulpin_provisional": null,
  "unit_type": "apartment",
  "status": "approved",
  "validation_state": "passed",
  "dispute_state": "undisputed",
  "lower_limit": 918.5,
  "upper_limit": 921.5,
  "crs": "EPSG:32643",
  "vertical_datum": "EGM2008",
  "source_ids": ["SRC-005"],
  "attributes": {
    "floor_index": 1,
    "floor_height_m": 3.0
  }
}
```

#### `POST /cadastre/units/{unit_id}/transition`
Transition record status (`Draft → Processing → Needs Review → Approved → Replaced → Closed`).

* **Request Body:**
```json
{
  "target_status": "approved",
  "actor": "reviewer_john",
  "comment": "Approved following boundary verification."
}
```
* **Response (200 OK):**
```json
{
  "unit_id": "APT-101",
  "status": "approved",
  "ulpin": "KA05B012345678-V1-A01-001-K"
}
```

---

### 4.2 GeoPackage Database Schema ([`store.py`](./store.py))

```sql
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

CREATE TABLE IF NOT EXISTS ulpin_ledger (
    ulpin         TEXT PRIMARY KEY,
    unit_id       TEXT NOT NULL,
    issued_at     TEXT NOT NULL,
    ulpin_version TEXT NOT NULL,
    state         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ulpin_sequence (
    parent_ulpin_14 TEXT NOT NULL,
    stratum         TEXT NOT NULL,
    level           INTEGER NOT NULL,
    unit_id         TEXT NOT NULL,
    sequence        INTEGER NOT NULL,
    PRIMARY KEY (parent_ulpin_14, stratum, level, unit_id)
);
```

---

### 4.3 Rule ID Reference Matrix

| Rule ID | Severity | Category | Description |
| :--- | :--- | :--- | :--- |
| `GEOM_INVALID` | `error` | Geometry | Malformed polygon / topological self-intersection |
| `GEOM_DUPLICATE` | `error` | Geometry | Identical footprint WKB hash + identical Z-limits |
| `Z_IMPOSSIBLE` | `error` | Geometry | Lower limit $\ge$ upper limit |
| `OVERLAP_SIBLING` | `error` | Topology | Non-easement sibling units penetrate vertically and horizontally beyond tolerance |
| `ESCAPES_PARENT` | `error` | Containment | Ownership unit extends beyond parent parcel (exempt for easements) |
| `UTILITY_CROSSES_BUILDING` | `error` | Crossing | Underground/elevated easement intersects a building or apartment volume |
| `FLOOR_SEQUENCE` | `error` | Sequence | Discontinuity / gap between consecutive floor slabs |
| `GAP_SIBLING` | `warning` | Topology | Unexplained gap between subdivided sibling flats |
| `FLOOR_HEIGHT_IMPLAUSIBLE` | `warning` | Attribute | Storey height outside $2.4\text{m} - 5.0\text{m}$ range |
| `CONFIDENCE_LOW` | `warning` | Provenance | AI model confidence score $< 0.60$ |
| `CRS_MISMATCH` | `error` | Metadata | Unit CRS differs from project reference system |
| `DATUM_MISMATCH` | `error` | Metadata | Unit vertical datum differs from project datum |
| `PROVENANCE_MISSING` | `info` | Metadata | Source accuracy missing, default tolerance applied |
