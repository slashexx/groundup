# groundup

**3D ULPIN generation and vertical property mapping.**
SIH 2026 · Problem Statement **SIH26011** · Ministry of Rural Development, Department of
Land Resources.

Land records today describe land as a flat polygon. That is adequate for a field and
inadequate for a city — nothing in the current system can uniquely identify a flat on the
seventh floor, the basement parking under it, or the water main running beneath both.

`groundup` extends India's existing 2D ULPIN into the third dimension: unique, verifiable
identities for surface parcels, the floors and apartments above them, and the utility
corridors below them.

---

## Repository

Single repository for the whole project — six blocks, six owners, everyone pushes here.

```
groundup/
├── contracts/              cross-team interfaces (JSON Schema)
│   ├── inbound/            what the cadastre block requires
│   ├── outbound/           what it emits
│   └── fixtures/           demo-parcel.json, defects deliberately planted
├── desktop/                P1 · Tauri review shell
├── sidecar/
│   ├── ingest/             P2 · CRS and datum harmonisation -> project GeoPackage
│   ├── ai/                 P3 · footprint detection and floor estimation
│   └── cadastre/           P4 · 3D units, ULPIN, validation
│       ├── models.py       domain types
│       ├── store.py        six tables, SQLite over the project GeoPackage
│       ├── extrude/        footprint + DEM/DSM -> building -> floors -> apartments
│       ├── ulpin/          minting, ledger, lifecycle state machine
│       ├── validate/       topology and provenance checks
│       ├── tools/          fixture generator, chain runner
│       └── tests/
├── viewer/                 P5 · Cesium + MapLibre components
└── web/                    P6 · read-only published viewer and publish pipeline
```

All six blocks are in the repository, each owned and added by its owner; nothing was
scaffolded for anyone in advance. They form one chain — P2 harmonises the sources, P4
turns them into identified volumes and checks them, P6 publishes the result to a
shareable link:

```bash
python3 sidecar/cadastre/tools/run_chain.py --gpkg pilot.gpkg
python3 -m uvicorn cadastre.app:app --app-dir sidecar --port 8000
cd web && pnpm publish:live --db pilot.gpkg
```

`sidecar/cadastre/` is the block that turns shapes into *owned volumes with names* and
then proves those volumes are mutually consistent. Everything upstream produces flat
geometry; everything downstream displays and exports. This is what makes the system a
cadastre rather than a 3D model viewer.

Owners: **dhruv** (rasters and spatial predicates) · **shankhanil** (identity, process,
schema).

---

## The idea in three parts

### 1. An identifier that extends rather than replaces

ULPIN already exists — the 14-character *Bhu-Aadhaar* issued under DILRMP by this same
department. It is strictly 2D. We keep those 14 characters intact as a parent key and
append a stratum, a level and a unit sequence:

```
KA05B012345678 - V1 - A07 - 003 - K      urn:ulpin:3d:v1:KA05B012345678:A:07:003
```

Every existing record still resolves. The version field exists because the official format
may change. The final character is an ISO 7064 MOD 37,36 check digit, measured to catch
**100% of single-character substitutions and 99.89% of adjacent transpositions**.

Crucially, identity and locator are separate: `unit_id` is opaque and permanent, while the
ULPIN is stamped at approval and frozen. Without that split, refining a point cloud by two
centimetres would mint a new identifier for a flat someone already owns.

### 2. Volumes built from evidence, not assumption

Buildings are extruded from a footprint plus a DEM and DSM — median ground level and
median roof plane, never the maximum, which would catch water tanks and antennas, and
never a high percentile, which would catch the parapet. Corrected for the plinth a
building sits on. Floors are divided from that usable height.

Where there is no interior data, **no apartments are invented**. The floor is recorded as
un-subdivided. Missing data is shown as missing.

### 3. Validation that knows what it can measure

Every unit is a prism, which means 3D intersection decomposes exactly into a 2D footprint
test and a z-interval test — no 3D boolean engine required, and watertightness comes free
by construction.

Comparison tolerances are **derived from the stated accuracy of the source data**, never
hardcoded. A five-centimetre overlap between footprints captured at thirty-centimetre
accuracy is measurement noise, not an encroachment. Reporting it would train reviewers to
click through warnings, which is how these systems actually fail — not through missed
errors, but through so much noise that nobody reads them.

And containment is type-conditional: an underground water main is an **easement**, not an
ownership volume. Crossing parcel boundaries is its normal condition. Ownership volumes
must not overlap; easement corridors are supposed to.

---

## Architecture

Desktop-first, file-based, serverless. The store is a single GeoPackage; the whole system
runs offline from one laptop. Python for the geospatial work — shapely, rasterio, pyproj,
geopandas — with no SpatiaLite, no PostGIS and no 3D boolean engine, because the prism
representation makes them unnecessary.

Known limitation, stated deliberately: **v1 is prism-only.** No mezzanines, cantilevers,
double-height rooms or sloped roofs. The schema carries a `representation` flag so
polyhedral units are a clean later extension.

Full rationale in [`.claude/02-architecture.md`](.claude/02-architecture.md).

---

## Standards

Designed against **ISO 19152 (LADM, 2nd ed.)**, with **CityGML 3.0** as the intended 3D
exchange format. Not decoration — a conformance statement is a credential a ministry
recognises.

---

## Getting started

```bash
python3 sidecar/cadastre/tools/make_fixture.py    # regenerate the demo fixture
python3 sidecar/cadastre/tools/run_chain.py       # run the whole chain over the sample data
pytest sidecar/cadastre/tests
python3 sidecar/cadastre/tools/mutation_check.py  # every guard must be load-bearing
ruff check sidecar/cadastre
```

The fixture at `contracts/fixtures/demo-parcel.json` is a complete scenario —
16 units across one parcel and its neighbour, with defects planted for every severity plus
two **negative tests** recording findings that must *not* fire. Downstream blocks build
against it before our real code exists.

---

## Documentation

**[`.claude/`](.claude/) is the single source of truth** for every decision, rationale and
specification. [`CLAUDE.md`](CLAUDE.md) indexes it and carries the rules for keeping it
current. This README is a derived summary and never holds anything absent from `.claude/`.
