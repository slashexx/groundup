#!/usr/bin/env python3
"""P2 -> P3 -> P4 in one command, so P6 has something real to publish.

The steps had to be run by hand in the right order, and getting the order wrong fails
quietly: publish a project that was ingested but never derived and the site renders flat
plates; publish one that was never validated and it renders "0 findings", which reads as
*checked and clean* rather than *never checked*. This runs them in order and says what
each one did.

    ./.venv/bin/python sidecar/cadastre/tools/run_chain.py [--gpkg pilot.gpkg]
                                                           [--no-rasters]
                                                           [--accept-ai-as NAME]

**AI suggestions stop at the queue unless a person is named.** `--accept-ai-as` takes
the name of whoever is running the chain and records it as the reviewer, because FR-05
does not say "a review happened", it says a human decided. It is a stand-in for P1's
review screen, not a bypass: without it the chain ends with the suggestions listed and
waiting, which is the correct resting state.

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
from cadastre import derive, detect, ingest_gpkg, suggestions, validate
from cadastre.store import init_schema, load_project, save_run

#: (sample file, contract layer, source id, source type) - P2's own sample data.
LAYERS = [
    ("sample_parcels.geojson", "parcel", "src-parcels", "parcel_map"),
    ("sample_buildings.geojson", "building_footprint", "src-bldgs", "footprint"),
]


STEPS = 7


def step(n: int, title: str) -> None:
    print(f"\n\033[1m[{n}/{STEPS}] {title}\033[0m")


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
    ap.add_argument("--accept-ai-as", metavar="NAME", default=None,
                    help="accept P3's suggestions as this person. Without it they stay in "
                         "the review queue, which is where FR-05 says they belong.")
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

        step(4, "P3 · detect buildings from the elevation surface")
        # The same call P1's AI screen makes over HTTP, so the chain exercises the route
        # the product uses rather than a path of its own.
        try:
            found = detect.DetectReport() if args.no_rasters else detect.run(conn, settings)
        except detect.AIUnavailable as err:
            raise SystemExit(f"{err}\nOr run with --no-rasters, which skips detection "
                             "along with the elevation it reads.") from err
        if not found.dsm_raster_id:
            print("    no DEM/DSM registered - nothing for the detector to read")
        else:
            print(f"    {found.found} found on {found.dsm_raster_id}/{found.dem_raster_id}, "
                  f"{found.stored} stored"
                  + (f", {len(found.already_reviewed)} already decided and left alone"
                     if found.already_reviewed else ""))
            for sg in suggestions.listing(conn, "pending"):
                a = sg["attributes"]
                print(f"    {sg['suggestion_id'][:8]}  confidence {sg['confidence']:.2f}  "
                      f"{a.get('floor_count')} storeys  "
                      f"roof {a.get('roof_level_m')} m  [{sg['review']['state']}]")

        step(5, "review · FR-05")
        if args.accept_ai_as:
            pending = suggestions.listing(conn, "pending")
            for sg in pending:
                suggestions.review(conn, sg["suggestion_id"], "accepted", args.accept_ai_as)
            applied = suggestions.apply(conn, settings)
            print(f"    {len(pending)} suggestions accepted by {args.accept_ai_as!r} -> "
                  f"{applied.created} new buildings ({applied.with_heights} with heights, "
                  f"{applied.minted} provisional ULPINs)")
            if applied.unresolved:
                print(f"    no parcel holds a majority of: {applied.unresolved}")
        else:
            waiting = len(suggestions.listing(conn, "pending"))
            print(f"    {waiting} suggestions left in the queue - an AI outline becomes a "
                  "unit only when a person accepts it (FR-05).")
            print("    pass --accept-ai-as NAME, or review them from P1.")

        step(6, "P4 · derive heights and floors")
        report = derive.derive_heights(conn)
        print(f"    {report.parcels_grounded} parcels grounded, "
              f"{report.heights_derived}/{report.buildings_seen} buildings given heights, "
              f"{report.floors_created} floors ({report.floors_identified} identified)")
        for uid in report.skipped_no_raster:
            print(f"    no raster covers {uid} - heights left absent (FR-03)")
        for uid in report.skipped_thin_coverage:
            print(f"    raster coverage too thin over {uid} - heights left absent (FR-03)")

        step(7, "P4 · validate")
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
