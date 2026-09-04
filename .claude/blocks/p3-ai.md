# P3 · AI Detection & Floor Estimation Engine

**Owner:** soumyadipta · **Path:** `sidecar/ai/`

## Scope

The AI detection engine responsible for extracting building footprints from 2D RGB aerial orthophotos and elevation rasters (DEM/DSM), calculating zonal elevation statistics (ground level, roof level), estimating floor counts via normalized Digital Surface Model ($\text{nDSM} = \text{DSM} - \text{DEM}$) analysis with FR-03 elevation fallback, and emitting provisional AI Suggestion JSON artifacts (`contracts/inbound/p3-suggestion.schema.json`) for human review in P1 (desktop application shell) and P5 (viewer).

```
sidecar/ai/
├── run_detection.py           CLI orchestrator supporting ONNX & hybrid detection
├── pyproject.toml             module dependencies & metadata
├── src/ai/
│   ├── models.py              Pydantic data models matching p3-suggestion schema
│   ├── yolo_detector.py       YOLOv8-seg / ONNX local inference detector for orthophotos
│   ├── ndsm_estimator.py      elevation statistics & floor height estimator
│   ├── footprint_extractor.py raster thresholding & polygon vectorization fallback
│   ├── hybrid_pipeline.py     hybrid YOLOv8 orthophoto + nDSM floor estimation engine
│   └── suggestion_builder.py  suggestion payload builder & JSON schema validator
└── tests/                     unittest test suite (8 tests)
```

```bash
cd sidecar/ai && python3 -m unittest discover -s tests -p "test_*.py"
```

## Interface with P4 (agreed at the contract surface)

The AI engine produces JSON suggestion files consumed by P4 per `contracts/inbound/p3-suggestion.schema.json`:

- **UUID Suggestion Identifier (`suggestion_id`)** — Unique UUID string identifying each candidate building outline or floor estimate.
- **Suggestion Kind (`kind`)** — `"building_outline"` or `"floor_estimate"`.
- **Projected Metric CRS Geometry (`geometry`)** — GeoJSON Polygon in the project's projected metric CRS (`EPSG:32643` / UTM Zone 43N).
- **Model Provenance (`model`)** — Captures model name (e.g. `yolov8s-seg-buildings`), version string (`1.0.0`), and execution timestamp `run_at`.
- **Zonal & Floor Attributes (`attributes`)** — Stores `floor_count`, `floor_count_method` (`ndsm_division`), `ground_level_m`, and `roof_level_m`.
- **Human-in-the-loop Review State (`review`)** — Initial state is strictly `"pending"`. P4 consumes **only** suggestions whose `review.state` is `"accepted"` or `"edited"` (enforcing FR-05 at the contract level).

## Architecture & Design Decisions (Matching P3 Block Diagram)

- **YOLOv8-seg / SAM → ONNX (Runs Locally)** — Serverless local ONNX inference engine (`yolo_detector.py`) executing via `onnxruntime` on CPU without external API dependencies or cloud GPU requirements.
- **2D Building Outlines from Orthophotos** — Extracts building boundaries from 2D RGB drone orthophotos and maps pixel predictions to spatial projected metric CRS coordinates (`EPSG:32643`).
- **Floor Estimation (DSM - DEM Rule Fallback)** — Combines YOLOv8 2D outlines with nDSM zonal statistics ($\text{nDSM} = \text{DSM} - \text{DEM}$) for 3D elevation & floor count estimation. In compliance with **FR-03**, if elevation rasters are absent, `floor_count` falls back to `None`.
- **Provisional Suggestion Format (FR-05)** — All AI suggestions are emitted with `review.state = "pending"` for human operator review in P1/P5 before P4 spatial unit conversion.

## Interfaces

- **`run_detection.process_ndsm_detection()` is what gets called**, not the CLI.
  `main()` parses its arguments and prints three lines without running a detection, and
  **that is deliberate, not a gap**: P1 is a Tauri app that declares no `externalBin` and
  spawns no process, so it reaches this work over HTTP or not at all. A working CLI would
  have no caller. `sidecar/cadastre/detect.py` invokes the nDSM path as a library behind
  `POST /cadastre/detect`, which is what P1's AI screen calls and what `run_chain.py`
  calls too, so the chain exercises the product's own route rather than a path of its own.
- The nDSM path is also the only one our pilot data can exercise: we have DEM/DSM rasters
  and no orthophoto, so the YOLO branch has nothing to read.
- **P4 never imports this package at module level.** `detect.p3_detector()` resolves it
  lazily, so the cadastre block installs, imports and tests without opencv or onnxruntime
  present — the route answers 503 with the pip command instead of the sidecar failing to
  start. See `06-contracts.md`.
- **Dependencies are declared but were not installed** in the repo's shared `.venv`, so
  this block's 12 tests could not even be *collected* here until 2026-09-04
  (`ModuleNotFoundError: cv2`). `pip install opencv-python-headless onnxruntime` fixes
  it; no CI runs them, so green means "somebody ran it locally".

## Two defects found when P4 first consumed this output (2026-09-04)

Both are about the *frame* the numbers are in rather than the numbers themselves, which
is why the existing suite could not see them — every assertion held, on the wrong grid.
Both are fixed in `run_detection.process_ndsm_detection`, with tests in this block's own
suite that were shown to fail without the fix.

- **Geometry came back in pixel indices, not project metres.** `extract_from_ndsm` takes
  an optional `transform` and falls back to the identity when it is absent; the
  orchestrator never passed one. Pixel indices and metres are both plain floats, so
  nothing downstream can tell them apart: P4 would have sited a building at (50, 50) in
  UTM 43N, roughly 276 km from its parcel and off the coast. The area filter was out by
  the square of the pixel size with it — at 0.5 m resolution, `min_footprint_area_m2 =
  15.0` was rejecting anything under 3.75 m². Measured on the demo rasters: without the
  transform, bounds `(50, 50, 114, 117)` and area 4207; with it, bounds
  `(276678.9, 2110599.7, 276710.9, 2110633.2)` and area 1039.8 m², matching to the
  centimetre the footprint the same building already has in the register.
- **Every building in a scene got the same elevation statistics.** `estimate_from_arrays`
  accepts a `mask`; the orchestrator passed the whole arrays, so ground level, roof level
  and storey count were computed over the entire tile once and copied to every polygon —
  the tallest and the shortest come back identical. It looked correct on a
  single-building tile, where the 90th percentile of the whole surface lands on the one
  roof present (measured: 924.99 whole-raster against 925.03 masked, ground truth 925.0),
  which is exactly why it survived until a second building appeared.

## Open: the roof estimator disagrees with P4's

`NDSMEstimator` takes the **90th percentile** of the DSM as the roof level. P4's
`extrude.raster.roof_level` deliberately takes the **median**, and a mutation guards it —
"parapet mistaken for the roof slab". On a building with a parapet the two differ by
roughly the parapet height, so an accepted suggestion records a building about a metre
taller than the same building derived from the same rasters. Nothing is wrong today
because the demo rasters put a parapet ring at slab + 1.0 m and the AI unit is the one
that gets flagged as a duplicate anyway; it needs a decision before real data.

## Observed state (2026-09-04)

Wired into the chain and reaching the published page. `run_chain.py` runs the detector
over the project's registered rasters, and on the pilot dataset it finds the one building
present at **confidence 0.90, 4 storeys, roof 925.03 m** against a ground truth of 925.0.

Suggestions stop in the review queue by default; `--accept-ai-as NAME` records that
person as the reviewer and applies them. Accepted, the building reaches P6 carrying its
identifier, `recorded by ai · confidence 90%`, and its source — and is immediately
flagged **OVERLAP_SIBLING** against the building P2 already delivered, because the
synthetic rasters were generated from that same footprint. That is the validator working:
the AI proposed a building the register already held, and it was caught before approval.

The block's own suite is 15 tests (12 existing plus 3 for the fixes above), passing.
