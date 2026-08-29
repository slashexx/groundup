# Architecture decisions

These are settled. Reopening a stack choice late costs a week. If one must change,
record why here.

## Shape of the system (team-level, affects us)

Desktop-first, file-based, **serverless**. No Postgres, no Docker, no backend service.
The store is a single **GeoPackage** file. The web deliverable is a *static export* of
approved units, published to static hosting. The whole system must run offline from one
laptop, because finale venues have unreliable internet — and the same property is what a
ministry wants, since they cannot use anyone's cloud account.

## Decisions that constrain our block

### Language: Python

We evaluated TypeScript seriously (JSTS is a faithful port of JTS, which GEOS and
therefore shapely descend from; rbush for indexing; geotiff.js for rasters) and the
attraction was real — with no Python, the sidecar disappears entirely, along with
PyInstaller bundling and cross-language contract generation.

**We stayed with Python** because the geospatial ecosystem is there: rasterio, shapely,
pyproj, geopandas are mature and the community answers exist. The cost we accept is the
sidecar and its packaging.

### GeoPackage is the STORE. Python is the COMPUTE. No SpatiaLite.

The original team plan said "checks in shapely / SpatiaLite SQL". The SpatiaLite half is
dropped:

- our checks need R-tree indexing, type-conditional rules and provenance-derived
  tolerances — miserable to express in SQL
- shapely 2.x is numpy-vectorised and is *faster* than row-by-row SQL predicates
- libspatialite is a native binary that would have to be bundled per platform inside
  Electron; dropping it removes a class of packaging failure

GeoPackage survives as the **file format** — one portable file, opens in QGIS, ships with
the demo. It is just SQLite, so our registry tables live in the same file via stdlib
`sqlite3`, alongside the spatial layers read with geopandas.

### No 3D boolean engine — prism-only, and this is a feature

We have no SFCGAL, no CGAL, no PostGIS. We do not need one, because every unit is a prism:

> Two units intersect **iff** their footprints intersect **AND** their z-intervals overlap.

Footprint intersection is shapely; interval overlap is `max(lo) < min(hi)`. Exact, and
faster than a real boolean would be.

This also means **"open 3D shapes that should be closed" is satisfied by construction** —
a prism over a valid closed polygon is always watertight. Say that out loud in the pitch;
it is a property earned by choosing the representation carefully.

**The cost, stated deliberately:** no mezzanines, cantilevers, double-height rooms or
sloped roofs. The `representation` flag makes polyhedral units a later extension. Owning a
known limit reads as engineering judgement; being caught by it reads as an oversight.

### laspy, not PDAL

PDAL is a C++ binary and painful inside PyInstaller. Everything downstream of ingest needs
only a **raster DSM/DEM**, never the point cloud itself.

### Never depend on a system GDAL

Use the `rasterio` / `fiona` PyPI wheels — they vendor their own GDAL. This is the single
thing that makes bundling Python into Electron tractable. A conda or Homebrew GDAL will
not survive PyInstaller.

### Contract source of truth: JSON Schema

Language-neutral, because our block is Python and the consumers are TypeScript. TS types
are generated from the schemas; we validate with `jsonschema`. One canonical artifact.

## Interfaces we assume from other blocks

We do not prescribe how they are built, only what we receive and emit.

- **From P2**: a harmonized GeoPackage in a single projected CRS (metres) with a `source`
  registry carrying **mandatory** `horizontal_accuracy_m` and `vertical_accuracy_m`.
  Those two columns are what our tolerance model runs on. See
  `contracts/inbound/p2-geopackage.md`.
- **From P3**: suggestion JSON. We consume **only** suggestions whose `review.state` is
  `accepted` or `edited`, which enforces FR-05 structurally rather than by convention.
- **To P1, P5, P6**: `unit.schema.json` and `finding.schema.json`.

## Non-goals for our block

Legal registration, ownership transfer, deed parsing, tax or payment features, nationwide
processing, claiming survey-grade accuracy the source data does not support.
