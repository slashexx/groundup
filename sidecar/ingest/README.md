# sidecar / ingest (P2: Geo Data Pipeline)

Python pipeline responsible for ingesting vector/raster spatial data, extracting metadata, harmonizing geometries into projected metric CRS (`EPSG:32643` / UTM), and outputting standard GeoPackage (`.gpkg`) datasets per `contracts/inbound/p2-geopackage.md`.

## Modules

- `src/pipeline/file_inspector.py`: Parses & inspects vector (`.geojson`, `.shp`, `.dxf`, `.kml`) and raster metadata.
- `src/pipeline/harmonizer.py`: Reprojects geometries to projected metric CRS in meters and repairs invalid polygons using `make_valid()`.
- `src/pipeline/gpkg_writer.py`: Writes harmonized layers (`parcel`, `building_footprint`, `utility_line`) into `.gpkg` and updates mandatory `source` accuracy registry.
- `src/pipeline/schema_manager.py`: Manages SQLite/GeoPackage project settings and source tables.
- `run_pipeline.py`: Main orchestrator entry point.

## Running Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
