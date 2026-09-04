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

## Observed state (2026-09-04)

Complete P3 AI Engine implemented in `sidecar/ai/` and passing automated test suite (`tests/test_p3_detection.py`). Verified end-to-end: YOLOv8 ONNX orthophoto segmentation, nDSM elevation fallback, floor count calculation, and contract JSON schema compliance.
