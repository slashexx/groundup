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
# ...plus P3's, if you want run_chain.py to invoke the detector:
./.venv/bin/pip install opencv-python-headless onnxruntime

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
curl -X POST localhost:8000/cadastre/derive   -H 'content-type: application/json' -d '{"db_path":"pilot.gpkg"}'
curl -X POST localhost:8000/cadastre/validate -H 'content-type: application/json' -d '{"db_path":"pilot.gpkg"}'
curl "localhost:8000/cadastre/document?db_path=pilot.gpkg"
```

AI suggestions take four calls, because FR-05 is a sequence and not a flag:

```bash
curl -X POST localhost:8000/cadastre/detect -H 'content-type: application/json' \
     -d '{"db_path":"pilot.gpkg"}'                            # runs P3, fills the queue
# ...or post a batch produced elsewhere, same contract gate either way:
curl -X POST localhost:8000/cadastre/suggestions -H 'content-type: application/json' \
     -d '{"db_path":"pilot.gpkg","suggestions":[ ... ]}'      # nothing becomes a unit here
curl "localhost:8000/cadastre/suggestions?db_path=pilot.gpkg&state=pending"   # the queue
curl -X POST "localhost:8000/cadastre/suggestions/$ID/review?db_path=pilot.gpkg" \
     -H 'content-type: application/json' -d '{"state":"accepted","actor":"bibisha"}'
curl -X POST localhost:8000/cadastre/suggestions/apply -H 'content-type: application/json' \
     -d '{"db_path":"pilot.gpkg"}'
```

`/cadastre/document` returns the whole project in the same shape as
`contracts/fixtures/demo-parcel.json`, which is what the viewer and the desktop shell
consume. Interactive docs at <http://localhost:8000/docs>.

### The whole chain in one command

Those four calls have to happen in that order, and getting it wrong fails quietly rather
than loudly: skip `derive` and the project is footprints with no heights; skip `validate`
and `/cadastre/document` reports `findings: []` for a project nobody checked, which reads
downstream as a clean bill of health. `run_chain.py` runs P2's pipeline and all of P4's
steps in order, in-process, and prints what each one did:

```bash
./.venv/bin/python sidecar/cadastre/tools/run_chain.py --gpkg pilot.gpkg
./.venv/bin/python sidecar/cadastre/tools/run_chain.py --gpkg dry.gpkg --no-rasters
./.venv/bin/python sidecar/cadastre/tools/run_chain.py --gpkg pilot.gpkg --accept-ai-as NAME
```

Seven steps: P2 harmonises, P4 imports, elevation is registered, **P3 detects**, a human
decides, P4 derives and validates. Without `--accept-ai-as` the suggestions stay in the
queue, which is where FR-05 says they belong — the flag names whoever is running the
chain and stands in for P1's review screen.

`--no-rasters` skips the synthetic elevation so the FR-03 path is visible: heights stay
absent, HEIGHTS_UNAVAILABLE is raised, and the record says why. That is the chain working,
not the chain failing. To publish the result, see `.claude/blocks/p6-web.md`.

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
├── detect.py             registered rasters -> P3 -> the review queue
├── suggestions.py        P3 -> P4: receive, review, apply. FR-05 lives here
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
│   ├── make_rasters.py   Synthetic DEM/DSM raster generator for tests
│   ├── make_demo_project.py  P2's pipeline over its samples -> a project GeoPackage
│   ├── make_demo_rasters.py  DEM/DSM covering a project's own buildings, registered
│   ├── run_chain.py      P2 -> ingest -> elevation -> derive -> validate, in order
│   └── mutation_check.py Removes each guard in turn; the suite must go red
│
└── tests/                Pytest suite (37 unit & property-based tests)
```

---

## 4. API & Schema Report

### 4.1 REST API Reference ([`api.py`](./api.py))

Nineteen operations across seventeen paths on `http://127.0.0.1:8000`, served by
`cadastre.app:app` — **not** `cadastre.api:router`, which uvicorn starts happily and
then answers 500 on every request. Interactive docs at `/docs`; `GET /` enumerates the
paths from the router itself.

**Every response below was captured from a running sidecar**, against a project built by
`tools/run_chain.py` over P2's sample data. Where a number looks oddly specific it is
because it is real.

Two conventions apply throughout:

- **`db_path` is a server-side filename, not an upload.** The sidecar and the desktop
  shell run on the same machine and share a filesystem — that is the whole premise of a
  file-based, serverless design. `GET` routes take it as a query parameter defaulting to
  `pilot.gpkg`; `POST` routes take it in the body.
- **`actor` is recorded, not authenticated.** This is a single-operator desktop tool. The
  name is evidence of who decided, which several requirements need; it is not a login.

| | Route | Purpose |
|---|---|---|
| | `GET /cadastre/health` | is the sidecar up |
| **P2 → P4** | `POST /cadastre/ingest` | import P2's layers as units |
| | `POST /cadastre/derive` | give buildings heights and a floor stack |
| **P3 → P4** | `POST /cadastre/detect` | run the detector, queue what it finds |
| | `POST /cadastre/suggestions` | take a batch from P3 |
| | `GET /cadastre/suggestions` | the review queue |
| | `POST /cadastre/suggestions/{id}/review` | a human accepts, edits or rejects |
| | `POST /cadastre/suggestions/apply` | reviewed suggestions become units |
| **Checking** | `POST /cadastre/validate` | run every rule, persist the result |
| | `GET /cadastre/runs/latest` | the most recent run and its findings |
| | `POST /cadastre/findings/{id}/acknowledge` | a reviewer accepts a warning |
| **Records** | `GET /cadastre/units/{unit_id}` | one unit, without its geometry |
| | `POST /cadastre/units/{unit_id}/transition` | move a unit through its lifecycle |
| | `GET /cadastre/ulpin/{ulpin}` | resolve an identifier, including a closed one |
| **P4 → P5/P6/P1** | `GET /cadastre/document` | the whole project in the outbound shape |

Status codes are used consistently and are worth typing against:

| Code | Means |
|---|---|
| `400` | the request is coherent but the domain forbids it — a transition the lifecycle does not allow, a review that is not a decision |
| `404` | no such unit, finding, suggestion or issued ULPIN |
| `409` | a guard refused: an error acknowledged instead of fixed, a suggestion re-decided after it became a unit, an identifier already issued |
| `422` | this is not a project, or not built far enough to answer — and, for suggestions, a payload the inbound contract refuses |
| `503` | P3 is not installed in this deployment. The request was fine |

---

#### `GET /cadastre/health`

```json
{ "status": "ok", "block": "cadastre" }
```

---

#### `GET /cadastre/source-types`

What a project may be built from. Served rather than hardcoded in P1 so the wizard's
form and `project.py` cannot drift: a type the form offers but the module does not
handle is a file the operator selects and the project silently ignores.

```json
{
 "vector": {"parcel_map": "parcel", "footprint": "building_footprint", "utility": "utility_line"},
 "raster": {"dem": "DEM", "dsm": "DSM", "ortho": "ORTHO"},
 "register_only": ["floorplan", "pointcloud", "survey_control"]
}
```

- **`vector`** — harmonized by P2 into the named contract layer, in the project CRS.
- **`raster`** — registered where the file sits and read by `derive`; not copied.
- **`register_only`** — provenance with no geometry P4 reads as a unit. `pointcloud` is
  here rather than under `raster` because P4 reads a DEM/DSM *derived* from a LAS/LAZ
  tile, never the tile itself.

---

#### `POST /cadastre/sources`

Appends sources to a project that already exists, and by default re-ingests so the new
layers become units. This is what an operator uses when the footprints arrive after the
parcels, or when elevation shows up later.

```json
{
 "db_path": "ward42.gpkg",
 "ingest": true,
 "sources": [
   {"path": "/data/buildings.geojson", "source_type": "footprint",
    "name": "Municipal footprint survey", "provider": "ULB",
    "capture_date": "2026-03-14", "crs": "EPSG:4326",
    "vertical_datum": "EGM2008",
    "horizontal_accuracy_m": 2.0, "vertical_accuracy_m": 5.0}
 ]
}
```

No project settings are accepted here, on purpose. The CRS, vertical datum and strata were
decided once at creation and every unit already carries them; letting a later upload
restate them would let two halves of one project disagree about where they are.

Nothing is deleted. Re-ingesting is safe to repeat because units are matched on their
source-local id, so adding footprints to a project that already holds its parcels keeps
those parcels and every identifier issued against them — the response reports `created`
and `reused` separately so it is visible which happened.

`404` if the path holds no project, `409` if it holds one the ingest block never finished
writing, `422` if a file is unreadable or missing.

#### `GET /cadastre/project`

Opens a project that already exists, and reports what it holds. Read-only: a path that is
not a project is refused rather than initialised as a blank one there.

```json
{
 "db_path": "/data/ward42.gpkg", "name": "ward42",
 "project_crs": "EPSG:32643", "vertical_datum": "EGM2008",
 "units": 5949, "unit_counts": {"land_parcel": 36, "building": 910, "floor": 5003},
 "sources": ["SRC-PARCEL-MAP-5dc19b", "SRC-FOOTPRINT-108ec4"]
}
```

Creating a project and opening one are different operations, and P1 only had the first.
A project built yesterday could be reached only by running the wizard over the same file
again — which is how the wizard came to overwrite one.

#### `POST /cadastre/project`

Builds a project GeoPackage from the operator's own files and imports it, in one call.
This is what P1's creation wizard posts. Everything else in this block consumes a project
that already exists; this is the route that makes one.

```json
{
 "db_path": "ward42.gpkg",
 "project_crs": "EPSG:32643", "vertical_datum": "EGM2008",
 "stratum_below_limit_m": -30.0, "stratum_above_limit_m": 150.0,
 "default_plinth_offset_m": 0.6, "default_parapet_deduction_m": 0.0,
 "ulpin_version": "v1", "ruleset_version": "r1",
 "sources": [
  {"path": "/data/ward42/parcels.geojson", "source_type": "parcel_map",
   "name": "Ward 42 parcel map", "provider": "Survey of India",
   "capture_date": "2026-03-11", "crs": "EPSG:4326", "vertical_datum": "EGM2008",
   "horizontal_accuracy_m": 0.30, "vertical_accuracy_m": 0.50}
 ]
}
```

```json
{
 "db_path": "ward42.gpkg",
 "sources": ["SRC-PARCEL-MAP-b941f9"], "layers": ["parcel"],
 "rasters": [], "registered_only": [],
 "units": 1, "relationships": 0, "provisional_ulpins": 1,
 "unresolved_buildings": []
}
```

Creation and ingest are one operation because a project holding no units is not a state
worth exposing: the wizard would need a second call to reach a usable project, and a
failure between the two leaves a file that looks like a project and answers every query
with nothing.

**Paths, not uploads.** The sidecar and P1 run on the same machine — that is the whole
desktop-first design — so a source is named by its path. A 12 GB point cloud is not
copied into the project folder to satisfy tidiness; `raster.path` exists to point at one
where it lies.

Five refusals, each with a test and a mutation:

- **`horizontal_accuracy_m` and `vertical_accuracy_m` are mandatory** and must exceed
  zero. `contracts/inbound/p2-geopackage.md` says so in bold: P4 derives every geometric
  tolerance from them via `tol = k * sqrt(acc_a² + acc_b²)`. P2's `process_file` defaults
  them to 0.20/0.25 m; this route refuses instead, because a default makes every source
  silently claim survey grade and turns measurement noise into reported encroachments.
  Genuinely unknown accuracy is recorded as a conservative number with
  `processing_status: "accuracy_estimated"` — never by omitting the field.
- **A non-zero `default_parapet_deduction_m` is refused.** `extrude.building` already
  raises `EstimatorMismatch` on it, but only at derive time — by then the project exists
  and the data is imported, and the field the operator must change is three screens back.
  The wizard is where a person types the number, so it is refused there too.
- **An unknown `source_type` is refused** and the error names the known ones.
- **A project needs at least one vector source.** A DEM is registered *against* a
  project; it cannot be the thing that starts one, and the GeoPackage does not exist as a
  file until a layer is written to it.
- **A missing file is named** before anything is built, rather than half-constructing a
  project around it.

---

#### `POST /cadastre/ingest`

Imports P2's `parcel`, `building_footprint` and `utility_line` layers as units.
Body: `{"db_path": "pilot.gpkg"}`.

```json
{
 "units": 2, "created": 0, "reused": 2,
 "relationships": 2, "provisional_ulpins": 2,
 "unresolved_buildings": []
}
```

- **`reused`** — units already present, matched by their P2 local id. Re-running after P2
  adds a layer does not mint a second identity for the same parcel, which is why the
  numbers above show `created: 0` on a second call.
- **`relationships`** — two per attachment, not one: a parcel holding a building yields
  both `contains` and `inside`. Validation walks the first; P5 builds a unit's parent from
  the second.
- **`unresolved_buildings`** — footprints no parcel holds a **majority** of. Imported
  without a parent rather than attached to a guess.

Imported units have **no height**: P2 registers rasters but does not deliver elevation
through the GeoPackage, so `lower_limit`/`upper_limit` are null and
`attributes.heights_unavailable` says why. `POST /cadastre/derive` fills them in.

---

#### `POST /cadastre/derive`

Turns registered DEM/DSM rasters into heights and floors. Body: `{"db_path": "..."}`.

```json
{
 "parcels_grounded": 1,
 "buildings_seen": 1,
 "heights_derived": 1,
 "floors_created": 5,
 "floors_identified": 5,
 "skipped_no_raster": [],
 "skipped_thin_coverage": []
}
```

- **`parcels_grounded`** — parcels whose legal column was anchored to the ground beneath
  them. `stratum_below/above_limit_m` are relative to ground at the parcel, not to the
  geoid; read absolutely they put the whole column below its own buildings.
- **`floors_identified`** — derived floors that received a provisional ULPIN. Lower than
  `floors_created` when a building carries no parent parcel: no parent, no identifier.
- **`skipped_*`** — buildings left with no height at all, and raised as
  `HEIGHTS_UNAVAILABLE` at validation. Absent data is reported, never invented (FR-03).

Repeatable: a second call sees no building lacking heights and reports `buildings_seen: 0`.
Returns **409** when the project has no `project_settings`.

---

#### `POST /cadastre/detect`

Runs P3 over the project's registered rasters and queues what it finds. Nothing here
becomes a unit. Body: `{"db_path": "..."}`.

```json
{
 "dem_raster_id": "RST-DEM",
 "dsm_raster_id": "RST-DSM",
 "found": 1,
 "stored": 0,
 "already_reviewed": [],
 "rediscovered": ["04e85409-a9b2-4ffb-b1c3-4deb3732d101"]
}
```

That is the response to pressing the button a **second** time. Detection is idempotent:
P3 mints a fresh `suggestion_id` every run, so a repeat would otherwise stack a second
identical outline behind the first — including behind one somebody had already rejected.
A detection recognised as one already in the project is reported under `rediscovered` and
not queued. Matching is on geometry, since the ids genuinely differ.

`dsm_raster_id: null` means the project has no elevation registered — reported, not
refused. **503** with the pip command when P3 is not installed here.

---

#### `POST /cadastre/suggestions`

Takes a batch from P3 directly, for a caller that ran the detector itself. Same contract
gate as `/detect`.

```json
{ "received": 1, "stored": 1, "already_reviewed": [] }
```

**All or nothing:** every entry is checked against
[`contracts/inbound/p3-suggestion.schema.json`](../../contracts/inbound/p3-suggestion.schema.json)
before any is written, so a batch carrying one malformed suggestion is refused whole
(**422**, naming the failing field) rather than half-imported. A suggestion whose id is
already present *and already decided* appears under `already_reviewed` and is left
untouched — re-running the detector must not erase what somebody chose.

A suggestion whose `crs` is not the project CRS is refused. Geometry is in the project CRS
in metres by contract and P4 does not reproject; a WGS84 polygon contains perfectly
plausible numbers and the building would simply be in the sea.

---

#### `GET /cadastre/suggestions`

The review queue. `?state=pending` is what a review screen opens; omit it for everything.

```json
{
 "count": 1,
 "suggestions": [{
   "suggestion_id": "04e85409-a9b2-4ffb-b1c3-4deb3732d101",
   "kind": "building_outline",
   "geometry": { "type": "Polygon", "coordinates": [[[276679.44, 2110633.25], "…"]] },
   "crs": "EPSG:32643",
   "source_raster_ids": ["RST-DSM", "RST-DEM"],
   "confidence": 0.9,
   "model": { "name": "yolov8s-seg-buildings", "version": "1.0.0", "run_at": "…" },
   "attributes": { "floor_count": 4, "floor_count_method": "ndsm_division",
                   "ground_level_m": 912.4, "roof_level_m": 925.03 },
   "review": { "state": "pending", "reviewed_by": null, "reviewed_at": null,
               "edited_geometry": null },
   "unit_id": null
 }]
}
```

Each entry is the inbound contract shape plus `unit_id`, which is null until the
suggestion has become a unit. Newest model run first.

---

#### `POST /cadastre/suggestions/{suggestion_id}/review`

**This route is FR-05.** An AI outline never becomes a unit without a person's name
against it, and there is no code path around this call.

```json
{ "state": "accepted", "actor": "bibisha" }
```
```json
{ "suggestion_id": "04e85409-…", "state": "accepted", "reviewed_by": "bibisha" }
```

- `state` is `accepted`, `edited` or `rejected`. `pending` is where a suggestion starts,
  not somewhere it returns to.
- `edited` **requires** `edited_geometry`, and P4 then uses that outline and not the one
  the model drew. Enforced here and again by a database `CHECK`, so the rule survives a
  caller that bypasses the API.
- An unsigned decision is refused (**400**), by the API and by a second `CHECK`.
- **409** once the suggestion has become a unit: the unit has its own lifecycle from that
  point, and rewinding would mean orphaning it or withdrawing an allocated identity.

---

#### `POST /cadastre/suggestions/apply`

Accepted and edited suggestions become building units. Body: `{"db_path": "..."}`.

```json
{
 "units": 1, "created": 1, "reused": 0,
 "provisional_ulpins": 1, "with_heights": 1,
 "unresolved_suggestions": []
}
```

Pending and rejected suggestions are **skipped silently** — that is the correct answer for
a batch: pending means nobody has looked, rejected means somebody said no. Repeatable: a
suggestion remembers the unit it produced, so a second call reports `reused` rather than
minting a second building.

The unit is created with `created_by: "ai"`, its `confidence_score` and its `model`
provenance, attached to its parcel by the same majority rule ingest uses and identified by
the same minting path. **`with_heights`** counts suggestions carrying *both* a ground and
a roof level; one without the other is not half a height.

---

#### `POST /cadastre/validate`

Runs every rule over the project and persists the run. Body: `{"db_path": "..."}`.

```json
{
 "run_id": "0e7a58b0-e271-45ec-bcbb-52167c5dea0a",
 "units": 8,
 "findings": 1,
 "by_severity": { "warning": 1 }
}
```

The run writes each covered unit's `validation_state` back, which is what the review
queue sorts by and what P5 colours the map by. A run is scoped to the units it looked at:
it never marks a unit it skipped.

---

#### `GET /cadastre/runs/latest`

```json
{
 "run_id": "0e7a58b0-…",
 "ruleset_version": "r1",
 "findings": [{
   "finding_id": "9e14d75e-d2cd-492a-a5a7-cab28fef1d32",
   "run_id": "0e7a58b0-…",
   "rule_id": "CONFIDENCE_LOW",
   "severity": "warning",
   "unit_id": "db1b50a3-…",
   "related_unit_ids": [],
   "message": "Model confidence 0.42 is below the review threshold 0.6.",
   "suggested_action": "Inspect the underlying evidence before approving.",
   "affected_geometry": null,
   "measured_value": 0.42,
   "tolerance": 0.6,
   "detected_at": "2026-09-04T14:01:36.345615+00:00",
   "acknowledged_by": null, "acknowledged_at": null,
   "resolved_by": null, "resolution_note": null
 }]
}
```

Findings follow [`contracts/outbound/finding.schema.json`](../../contracts/outbound/finding.schema.json).
`measured_value` against `tolerance` is what lets a reviewer judge a finding rather than
just read it. **404** when no run has ever been recorded — which is *"we cannot verify
this"*, not *"there is nothing to verify"*.

---

#### `POST /cadastre/findings/{finding_id}/acknowledge`

A reviewer accepts a warning. Body: `{"actor": "bibisha"}`.

```json
{ "finding_id": "9e14d75e-…", "acknowledged_by": "bibisha" }
```

**Errors are not acknowledgeable** — 409:

```json
{ "detail": "09c3b2d4-… is an error, which cannot be acknowledged. Correct the unit and re-run validation." }
```

Approval requires zero errors *and* every warning acknowledged, so this route is what
unblocks it.

---

#### `GET /cadastre/units/{unit_id}`

One unit without its geometry — a review list does not draw anything, and a footprint per
row is a lot of bytes. Use `/cadastre/document` for the full record.

```json
{
 "unit_id": "9175aff7-f9dd-473f-bef2-80a682f1b536",
 "ulpin": null,
 "ulpin_provisional": "27402015001234-V1-S00-000-3",
 "unit_type": "land_parcel",
 "status": "needs_review",
 "validation_state": "passed",
 "dispute_state": "undisputed",
 "lower_limit": 882.3998718261719,
 "upper_limit": 1062.3998718261719,
 "crs": "EPSG:32643",
 "vertical_datum": "EGM2008",
 "source_ids": ["src-parcels"],
 "attributes": {
   "local_id": "P2026_PARCEL_001",
   "parent_ulpin_14": "27402015001234",
   "ground_level_m": 912.4,
   "stratum_is_relative_to_ground": true
 }
}
```

`ulpin` is null until approval and frozen thereafter; `ulpin_provisional` is recomputed
freely until then and discarded at approval. They are not the same field with two names —
see §2.1. `lower_limit: null` means **unknown**, never zero.

---

#### `POST /cadastre/units/{unit_id}/transition`

```json
{ "target_status": "approved", "actor": "bibisha",
  "comment": "boundary checked against the mutation register" }
```
```json
{ "unit_id": "9175aff7-…", "status": "approved",
  "ulpin": "27402015001234-V1-S00-000-3" }
```

Approval is the only transition with a side effect: it **freezes the ULPIN and writes the
ledger row**. It is refused unless a validation run exists, that run has zero errors, and
every warning on the unit is acknowledged. An absent run means *we cannot verify this*,
so approval fails closed.

- **400** — the lifecycle forbids it: `{"detail": "Cannot transition from needs_review to closed"}`
- **409** — the ledger refuses: no parent parcel to mint under, or the identifier is
  already issued

---

#### `GET /cadastre/ulpin/{ulpin}`

```json
{
 "ulpin": "27402015001234-V1-S00-000-3",
 "urn": "urn:ulpin:3d:v1:27402015001234:S:00:000",
 "unit_id": "9175aff7-f9dd-473f-bef2-80a682f1b536",
 "issued_at": "2026-09-04T14:01:14.627365+00:00",
 "ulpin_version": "v1",
 "state": "issued",
 "parent_ulpin_14": "27402015001234",
 "version": 1,
 "stratum": "S",
 "level": 0,
 "sequence": 0
}
```

A **closed or replaced** unit still answers: the identifier is retained forever and never
reissued, so "this was closed on that date" is a valid answer rather than a 404. `urn` is
the machine-readable form FR-06 requires.

- **400** — malformed, or the ISO 7064 check character fails. Checked before touching the
  database, so a typo cannot become a lookup
- **404** — a well-formed identifier that has never been issued

---

#### `GET /cadastre/document`

The whole project in one payload — what P5 renders, what P6 publishes and what P1's
dashboard counts.

```json
{
 "project": { "project_crs": "EPSG:32643", "vertical_datum": "EGM2008",
              "stratum_below_limit_m": -30.0, "stratum_above_limit_m": 150.0,
              "default_plinth_offset_m": 0.6, "default_parapet_deduction_m": 0.0,
              "ulpin_version": "v1", "ruleset_version": "r1" },
 "units": ["…"],
 "relationships": [{ "from_unit_id": "…", "to_unit_id": "…", "rel_type": "contains" }],
 "findings": ["…"],
 "expected_findings": ["…"]
}
```

- `units[]` follows [`contracts/outbound/unit.schema.json`](../../contracts/outbound/unit.schema.json),
  `findings[]` follows [`finding.schema.json`](../../contracts/outbound/finding.schema.json).
  Those files are the single definition of those shapes; nothing restates them.
- **This is the same shape as [`contracts/fixtures/demo-parcel.json`](../../contracts/fixtures/demo-parcel.json)**,
  which is what makes the fixture and this endpoint interchangeable for a consumer.
- Findings appear under **both** `findings` and `expected_findings`. The fixture uses the
  latter, because there they are an expectation rather than a result; emitting both means
  a consumer written against the fixture works here with no coordinated change.
- Coordinates are in the **project CRS, in metres** — a deliberate deviation from RFC 7946
  so P4 never reprojects per operation. Consumers reproject once, at load.
- **422** when the GeoPackage is not a project, or has not been ingested. A mistyped
  `db_path` arrives here as a blank database, because `sqlite3.connect` creates an empty
  file rather than failing, so the detail names the path and the ingest call.

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
