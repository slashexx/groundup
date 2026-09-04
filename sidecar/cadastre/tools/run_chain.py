#!/usr/bin/env python3
"""P2 -> P4 in one command, so P6 has something real to publish.

Five steps had to be run by hand in the right order before the published viewer could
show anything but footprints, and getting the order wrong fails quietly: publish a
project that was ingested but never derived and the site renders flat plates; publish one
that was never validated and it renders "0 findings", which reads as *checked and clean*
rather than *never checked*. This runs them in order and says what each one did.

    ./.venv/bin/python sidecar/cadastre/tools/run_chain.py [--gpkg pilot.gpkg]
                                                           [--no-rasters]

Then, to publish:

    ./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000
    cd web && pnpm publish:live --db <the gpkg>

`--no-rasters` skips the synthetic elevation, which is how you see what the chain does
with a project that genuinely has no DEM: heights stay absent, HEIGHTS_UNAVAILABLE is
raised, and the record says so. That is FR-03 working, not the chain failing.

In-process rather than over HTTP: the sidecar is P6's interface, not P4's own, and a
chain runner that needed a server running to prepare a file would be one more ordering
mistake to make.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sidecar"))
sys.path.insert(0, str(REPO / "sidecar/ingest"))

import make_demo_rasters  # sibling tool: build() and register()
from cadastre import derive, ingest_gpkg, validate
from cadastre.store import init_schema, load_project, save_run

#: (sample file, contract layer, source id, source type) - P2's own sample data.
LAYERS = [
    ("sample_parcels.geojson", "parcel", "src-parcels", "parcel_map"),
    ("sample_buildings.geojson", "building_footprint", "src-bldgs", "footprint"),
]


def step(n: int, title: str) -> None:
    print(f"\n\033[1m[{n}/5] {title}\033[0m")


def p2_pipeline(out: Path) -> None:
    """Run P2's pipeline over its sample data, writing the project GeoPackage."""
    from run_pipeline import GeoDataPipeline

    out.unlink(missing_ok=True)
    pipeline = GeoDataPipeline(gpkg_output_path=str(out))
    pipeline.setup_project()
    samples = REPO / "sidecar/ingest/test_data"
    for name, layer, source_id, source_type in LAYERS:
        if not pipeline.process_file(str(samples / name), layer, source_id, source_type):
            raise SystemExit(f"P2 pipeline failed on {name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gpkg", default=str(REPO / "pilot.gpkg"),
                    help="project GeoPackage to build (default: ./pilot.gpkg)")
    ap.add_argument("--no-rasters", action="store_true",
                    help="skip synthetic elevation - heights stay absent, as FR-03 requires")
    args = ap.parse_args()
    gpkg = Path(args.gpkg).resolve()

    step(1, f"P2 · harmonize sample data into {gpkg.name}")
    p2_pipeline(gpkg)

    conn = sqlite3.connect(gpkg)
    conn.row_factory = sqlite3.Row
    try:
        step(2, "P4 · ingest layers as units")
        init_schema(conn)
        settings = load_project(conn)[3]
        imported = ingest_gpkg.import_project(conn, settings)
        print(f"    {len(imported.units)} units ({imported.created} new, {imported.reused} reused), "
              f"{len(imported.relationships)} relationships, "
              f"{imported.minted} provisional ULPINs")
        if imported.unresolved:
            print(f"    unresolved buildings (no parcel holds a majority): {imported.unresolved}")

        step(3, "elevation" + (" · skipped (--no-rasters)" if args.no_rasters else ""))
        if args.no_rasters:
            print("    no DEM/DSM registered - buildings keep no height, by design")
        else:
            dem, dsm, meta = make_demo_rasters.build(conn, gpkg.parent / "rasters")
            make_demo_rasters.register(conn, dem, dsm)
            print(f"    synthetic DEM/DSM in {dem.parent} " +
                  ", ".join(f"{k}={v['storeys']} storeys" for k, v in meta.items()))

        step(4, "P4 · derive heights and floors")
        report = derive.derive_heights(conn)
        print(f"    {report.parcels_grounded} parcels grounded, "
              f"{report.heights_derived}/{report.buildings_seen} buildings given heights, "
              f"{report.floors_created} floors ({report.floors_identified} identified)")
        for uid in report.skipped_no_raster:
            print(f"    no raster covers {uid} - heights left absent (FR-03)")
        for uid in report.skipped_thin_coverage:
            print(f"    raster coverage too thin over {uid} - heights left absent (FR-03)")

        step(5, "P4 · validate")
        units, rels, sources, settings = load_project(conn)
        result = validate.run(units, rels, sources, settings)
        save_run(conn, result, [u.unit_id for u in units])
        by_severity: dict[str, int] = {}
        for f in result.findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
        print(f"    run {result.run_id} over {len(units)} units: "
              f"{len(result.findings)} findings {by_severity or '- clean'}")
        for f in result.findings:
            print(f"    {f.severity.value:<7} {f.rule_id.value} {f.unit_id}")
    finally:
        conn.close()

    print("\n\033[1mpublish:\033[0m")
    print("  ./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000")
    print(f"  cd web && pnpm publish:live --db {gpkg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
