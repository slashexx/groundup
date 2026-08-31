# P2 · geo data pipeline

**Owner:** soumyadipta · **Path:** `sidecar/ingest/`

## Scope

The GIS ingestion, CRS reprojection, and GeoPackage database management engine consumed by P1 (desktop application shell), P3 (AI detection), and P4 (3D units and validation). Accepts raw vector maps (`.geojson`, `.shp`, `.dxf`, `.kml`) and elevation rasters (`.tif`, DEM/DSM), extracts metadata, repairs invalid geometry, reprojects coordinates into project-standard projected metric CRS (`EPSG:32643` / UTM), and persists harmonized spatial layers into `.gpkg`.

```
sidecar/ingest/
├── run_pipeline.py            the orchestrator entry point
├── src/pipeline/
│   ├── file_inspector.py     metadata parser (vector + raster)
│   ├── harmonizer.py         pyproj reprojection & shapely make_valid()
│   ├── gpkg_writer.py        pyogrio SQLite layer writer & registry logger
│   └── schema_manager.py     GeoPackage project_settings & source tables
├── test_data/                 sample vectors (WGS84, UTM, buildings)
└── tests/                     unittest test suite
```

```bash
cd sidecar/ingest && python3 -m unittest discover -s tests -p "test_*.py"
```

## Interface with P4 (agreed at the contract surface)

The ingestion pipeline produces the harmonized GeoPackage (`.gpkg`) consumed by P4 per `contracts/inbound/p2-geopackage.md`:

- **Projected Metric CRS (`EPSG:32643`)** — Geometries are reprojected into UTM Zone 43N (metres) upon ingestion. P4 performs distance, area, and volumetric math directly without per-operation reprojection overhead.
- **`parcel` layer** — Stores `parcel_local_id`, `parent_ulpin_14` (optional 2D Bhu-Aadhaar key), `source_id` (FK → `source`), and `geom` (POLYGON in metres).
- **`building_footprint` layer** — Stores `building_local_id`, `parcel_local_id` (optional), `source_id` (FK → `source`), and `geom` (POLYGON in metres).
- **`utility_line` layer** — Stores `utility_local_id`, `utility_kind`, `stratum`, `depth_top_m`, `depth_bottom_m`, `corridor_width_m`, `source_id`, and `geom` (LINESTRING).
- **`source` registry table** — **Mandatory accuracy driver for P4 validation.** Stores `source_id`, `source_type`, `crs`, `vertical_datum`, **`horizontal_accuracy_m`**, **`vertical_accuracy_m`**, `coverage_wkt`, and `processing_status`. P4 derives all geometric tolerances from these accuracy bounds: $tol = k \cdot \sqrt{acc_a^2 + acc_b^2}$.
- **`project_settings` table** — Single-row table persisting `project_crs` (`EPSG:32643`), `vertical_datum` (`EGM2008`), stratum height limits (`-30 m` / `+150 m`), default plinth offsets (`0.6 m`), parapet deductions (`0.0 m`), `ulpin_version` (`v1`), and `ruleset_version` (`r1`).

## Decisions

- **`pyogrio` engine over default Fiona** — Uses `pyogrio` C-library binding for fast GDAL vector IO to guarantee proper GeoPackage SQLite table creation (`gpkg_contents`, `gpkg_spatial_ref_sys`) without schema corruption during append operations.
- **Automatic geometry repair (`make_valid()`)** — Self-intersecting ("bowtie") polygons and degenerate geometries are cleaned automatically during harmonization to prevent downstream topology validation crashes in P4.
- **Missing CRS fallback** — Source files lacking CRS tags default safely to `EPSG:4326` (WGS84) with a recorded warning rather than failing ungracefully.
- **Single-column geometry naming (`geom`)** — Standardizes all GeoDataFrame geometry columns to `geom` matching the contract schema.
- **Dynamic Surveyor Attribute Mapping** — Provides `column_mapping` parameter on `process_file()` to map arbitrary surveyor column names (e.g. `survey_no`) directly to contract attributes (`parent_ulpin_14`).

## Observed state (2026-08-30)

Core engine fully implemented and passing 10/10 automated integration and robustness tests (`tests/test_p2_pipeline.py`, `tests/test_p2_robustness.py`, `tests/test_p2_advanced.py`). Verified end-to-end: WGS84 parsing, UTM metric reprojection, utility line corridor creation, empty GeoDataFrame handling, and SQLite schema contract compliance.
