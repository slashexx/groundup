#!/usr/bin/env python3
"""Build the Trivandrum pilot project by running P2 over the real footprints.

Real building geometry from Microsoft's Global ML Building Footprints; a stand-in parcel
extent, because Kerala's Bhunaksha geometry is in a local grid with no published
projection. See data/trivandrum/README.md for exactly what is real here and what is not.

    ./.venv/bin/python sidecar/cadastre/tools/make_trivandrum_project.py [out.gpkg]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sidecar/ingest"))

from run_pipeline import GeoDataPipeline

DATA = REPO / "data/trivandrum"

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else DATA / "pilot.gpkg").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    pipeline = GeoDataPipeline(str(out))

    # Accuracy is declared per source, and honestly. The footprints are ML-derived from
    # satellite imagery, not surveyed - Microsoft's own accuracy discussion puts them at
    # metre scale, so claiming survey precision here would tighten every downstream
    # tolerance and turn ordinary imprecision into reported encroachments.
    pipeline.process_file(
        str(DATA / "parcels.geojson"), layer_name="parcel",
        source_id="SRC-TVM-PARCEL", source_type="parcel_map",
        source_name="Stand-in ward extent (not surveyed cadastre)",
        horizontal_accuracy_m=5.0, vertical_accuracy_m=5.0)

    pipeline.process_file(
        str(DATA / "buildings.geojson"), layer_name="building_footprint",
        source_id="SRC-TVM-MSFT", source_type="footprint",
        source_name="Microsoft Global ML Building Footprints 2026-08-13",
        horizontal_accuracy_m=2.0, vertical_accuracy_m=5.0)

    print(f"\nwrote {out}")
    print("next, with the sidecar running from that folder:")
    print("  POST /cadastre/ingest      then  tools/make_demo_rasters.py")
    print("  POST /cadastre/derive      then  POST /cadastre/validate")
