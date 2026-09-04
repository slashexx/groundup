# Contracts

`contracts/` is the only cross-team surface. **JSON Schema is the source of
truth** — language-neutral, because our block is Python and every consumer is TypeScript.
TS types are generated from these; we validate with `jsonschema`.

Changing a schema is a team decision, not an individual one. Freeze early, change by
agreement.

## Inbound — what we require

### `inbound/p2-geopackage.md` (from the geo pipeline)

A harmonized `.gpkg` in a single **projected** CRS in metres — we do area and distance
maths and must not reproject per operation.

Layers: `parcel`, `building_footprint`, optional `utility_line`.
Registry tables: `source`, `raster`, `project_settings`.

**The two columns that matter most:** `source.horizontal_accuracy_m` and
`source.vertical_accuracy_m` are **mandatory**. Every geometric comparison tolerance is
derived from them. If they are NULL we cannot distinguish a real encroachment from
measurement noise and fall back to flagging everything, making the review queue useless.
If accuracy is genuinely unknown, record a conservative estimate and set
`processing_status = 'accuracy_estimated'` — never leave it NULL.

`vertical_datum` is likewise required **per source**, for the reason in `05-validation.md`.

### `inbound/p3-suggestion.schema.json` (from AI detection)

Building outlines and floor estimates with confidence, model name/version/run time, and a
`review` block.

**We consume only suggestions whose `review.state` is `accepted` or `edited`.** That
enforces FR-05 structurally rather than by convention: an AI suggestion cannot become a
unit without a human. When state is `edited`, use `review.edited_geometry`, not `geometry`.

`floor_count_method: "ndsm_division"` is a **guess** and must arrive with low confidence,
or FR-03 is violated downstream.

## Outbound — what we emit

### `outbound/unit.schema.json`
Consumed by the desktop review screen, the viewer, and the export path.

Conditional constraints encoded in the schema itself:
- `status == approved` ⟹ `ulpin` is non-null (approval freezes the binding)
- `created_by == ai` ⟹ `confidence_score` and `model` are required (FR-05 provenance)

### `outbound/finding.schema.json`
`error | warning | info`, with `affected_geometry` so the viewer can draw it, plus
`measured_value` and the `tolerance` it was compared against — so a reviewer can see *why*
something was flagged, not just that it was.

## A deliberate deviation from RFC 7946

Every `footprint_2d` and `affected_geometry` is a GeoJSON geometry **in the project's
projected CRS (metres), not WGS84.** This is stated in both schemas. Reprojecting per
operation would be slow and would introduce rounding into exactly the comparisons whose
precision we care about.

## Fixture

`contracts/fixtures/demo-parcel.json` — see `05-validation.md`. It is a contract in
practice: downstream teams build against it before our real code exists.

## The integration surface

Schemas describe shapes. These are the routes that actually move them between blocks,
added when P1, P2, P4 and P5 were first wired together.

### `POST /cadastre/ingest` — P2 → P4

Reads P2's `parcel`, `building_footprint` and `utility_line` layers out of the project
GeoPackage and persists them as units and containment relationships. Implemented in
`sidecar/cadastre/ingest_gpkg.py`. Three refusals are load-bearing and each has a
mutation guarding it:

- A parcel with no `parent_ulpin_14` gets **no provisional ULPIN at all**, rather than
  one minted under a placeholder parent.
- Imported units have **no height**. P2 registers rasters but does not deliver DEM/DSM
  through the GeoPackage, so `lower_limit`/`upper_limit` are `None` and
  `attributes.heights_unavailable` says why. `extrude` fills them in when rasters exist.
- A building is attached to a parcel only when that parcel holds **more than half** its
  footprint. See `03-design.md` for why the threshold is a share rather than
  `intersects`.

Re-running the import is safe: `unit_id` is looked up by `attributes.local_id`, never
re-derived, so a second run reuses the identities the first one allocated.

**Containment is stored as a pair.** A parcel holding a building yields both
`contains` (parcel → building) and `inside` (building → parcel), and both halves are
load-bearing: validation walks `contains`, while `viewer/src/lib/adapter.ts` builds a
unit's `parent_id` from `inside` **alone**. Ingest wrote only `contains` until
2026-09-04, so every live-published building appeared to have no parcel above it and the
extract panel's lineage opened at the building — the wrong way round for a land record.
The fixture and `derive` had stored both directions all along, which is why nothing
caught it until P6 published live data rather than the fixture. If a rule or a consumer
ever needs only one direction, it is still both that get written.

### `GET /cadastre/document` — P4 → P5, P6, P1

The whole project in one payload: `project`, `units`, `relationships`, `findings`. It is
**the same shape as `contracts/fixtures/demo-parcel.json`**, which is what makes it a
drop-in replacement for the fixture in P5's `fromP4Document()`.

**It answers 422, never 500, for a GeoPackage that is not a project.** `sqlite3.connect`
creates an empty file for a path that does not exist, so a mistyped `db_path` reaches the
endpoint as a blank database rather than as an error; `store.load_project` now guards its
reads of `unit` and `unit_relationship` the way it always guarded P2's `source` and
`project_settings`, and the detail names the path and the ingest call. A consumer can
therefore treat 422 as "not a project yet" and 500 as a genuine bug.

That claim is about the shape, not about the values. Two differences are real and a
consumer should expect them: the fixture's `land_parcel`s carry frozen `ulpin`s while
live units in `needs_review` carry only `ulpin_provisional`, and 14 of the fixture's 16
units are deliberately `unvalidated` where a live document that has been through
`/cadastre/validate` has none. P6's publish gate turns on exactly that second difference —
see `blocks/p6-web.md`.

Findings are published under both `findings` and `expected_findings`. The fixture uses
the latter because there they are an *expectation*; live they are a *result*. Emitting
both means a consumer written against the fixture works against the endpoint with no
coordinated change. `viewer/src/lib/adapter.ts` reads `findings ?? expected_findings`.

### The application object

`sidecar/cadastre/app.py` is the ASGI app. **`api.router` is an `APIRouter`, not an
application**: uvicorn starts with it as a target — it is technically an ASGI callable —
and then answers **500 on every route**. The README documented that command for a while
and it never worked. Run `cadastre.app:app`.

CORS is an explicit origin list (the Tauri devUrl `:1420`, Vite `:5173`, packaged
`tauri://localhost`), not `*`: the sidecar listens on localhost while a browser is open
on the same machine, and a wildcard would let any page the reviewer visits read the
project.
