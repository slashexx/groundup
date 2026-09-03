# P3 · AI Detection & Floor Estimation Engine

**Owner:** soumyadipta · **Path:** `sidecar/ai/`

## Scope

The AI detection engine responsible for extracting building footprints from orthophotos/elevation rasters (DEM/DSM), calculating zonal elevation statistics (ground level, roof level), estimating floor counts via normalized Digital Surface Model ($\text{nDSM} = \text{DSM} - \text{DEM}$) analysis, and emitting provisional AI Suggestion JSON artifacts (`contracts/inbound/p3-suggestion.schema.json`) for human review in P1 (desktop application shell) and P5 (viewer).

```
sidecar/ai/
├── run_detection.py           the orchestrator entry point / CLI
├── pyproject.toml             module dependencies & metadata
├── src/ai/
│   ├── models.py              Pydantic data models matching p3-suggestion schema
│   ├── ndsm_estimator.py      elevation statistics & floor height estimator
│   ├── footprint_extractor.py raster thresholding & polygon vectorization
│   └── suggestion_builder.py  suggestion payload builder & JSON schema validator
└── tests/                     unittest test suite
```

```bash
cd sidecar/ai && python3 -m unittest discover -s tests -p "test_*.py"
```

## Interface with P4 (agreed at the contract surface)

The AI engine produces JSON suggestion files consumed by P4 per `contracts/inbound/p3-suggestion.schema.json`:

- **UUID Suggestion Identifier (`suggestion_id`)** — Unique UUID string identifying each candidate building outline or floor estimate.
- **Suggestion Kind (`kind`)** — `"building_outline"` or `"floor_estimate"`.
- **Projected Metric CRS Geometry (`geometry`)** — GeoJSON Polygon in the project's projected metric CRS (`EPSG:32643` / UTM Zone 43N).
- **Model Provenance (`model`)** — Captures model name (e.g. `yolov8s-seg-buildings`), version string, and execution timestamp `run_at`.
- **Zonal & Floor Attributes (`attributes`)** — Stores `floor_count`, `floor_count_method` (`ndsm_division`), `ground_level_m`, and `roof_level_m`.
- **Human-in-the-loop Review State (`review`)** — Initial state is strictly `"pending"`. P4 consumes **only** suggestions whose `review.state` is `"accepted"` or `"edited"` (enforcing FR-05 at the contract level).

## Decisions

- **Serverless nDSM Elevation Analysis** — Uses fast, array-vectorized NumPy & Rasterio operations to compute height differences ($\text{nDSM} = \text{DSM} - \text{DEM}$) over parcel/building bounds without heavy external GPU backend runtime requirements.
- **Percentile Elevation Filtering** — Uses median / 90th percentile elevation sampling within footprint bounds to eliminate vegetation noise and chimney spikes when calculating `roof_level_m`.
- **Low-Confidence Missing Data Fallback** — In compliance with FR-03, if raster height data is missing or invalid, `floor_count` is left as `None` with `confidence = 0.0` rather than making inaccurate guesses.
- **Strict JSON Schema Validation** — Outbound suggestions are validated using `jsonschema` against `contracts/inbound/p3-suggestion.schema.json` prior to emission.

## Observed state (2026-09-04)

Core engine fully implemented in `sidecar/ai/` and passing automated test suite (`tests/test_p3_detection.py`). Verified end-to-end: nDSM height calculation, floor count estimation, polygon vectorization, and JSON schema compliance.
