#!/usr/bin/env python3
"""Build a demo project GeoPackage by running the ingest block over its sample data.

The point is to exercise the real P2 -> P4 seam rather than hand-write a file that
happens to have the right tables: the GeoPackage this produces is the one P2's pipeline
actually writes, including the GeoPackage-flavoured geometry blobs that plain WKB
parsers choke on.

    ./.venv/bin/python sidecar/cadastre/tools/make_demo_project.py [out.gpkg]

Then, with the sidecar running:

    curl -X POST localhost:8000/cadastre/ingest \
         -H 'content-type: application/json' -d '{"db_path":"pilot.gpkg"}'
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sidecar/ingest"))

from run_pipeline import GeoDataPipeline

#: (sample file, contract layer, source id, source type)
LAYERS = [
    ("sample_parcels.geojson", "parcel", "src-parcels", "parcel_map"),
    ("sample_buildings.geojson", "building_footprint", "src-bldgs", "footprint"),
]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "pilot.gpkg"
    out = out.resolve()
    out.unlink(missing_ok=True)

    pipeline = GeoDataPipeline(gpkg_output_path=str(out))
    pipeline.setup_project()

    samples = REPO / "sidecar/ingest/test_data"
    for name, layer, source_id, source_type in LAYERS:
        ok = pipeline.process_file(str(samples / name), layer, source_id, source_type)
        if not ok:
            print(f"FAILED on {name}")
            return 1

    print(f"\nwrote {out}")
    print("next:")
    print(f'  curl -X POST localhost:8000/cadastre/ingest   -H "content-type: application/json" -d \'{{"db_path":"{out}"}}\'')
    print(f'  curl -X POST localhost:8000/cadastre/validate -H "content-type: application/json" -d \'{{"db_path":"{out}"}}\'')
    print(f'  curl "localhost:8000/cadastre/document?db_path={out}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
