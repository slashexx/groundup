#!/usr/bin/env python3
"""Generate DEM/DSM covering a project's building footprints, and register them.

The pilot dataset carries no elevation, so the demo chain stops at footprints: no
heights, no floors, nothing approvable. This synthesises terrain that actually covers
the project's own buildings and registers it in P2's `raster` table, so `derive` has
something to read.

Synthetic, and labelled as such in the source registry - `provider` says so, and the
accuracy recorded is the accuracy of the simulation, not a claim about survey quality.

    ./.venv/bin/python sidecar/cadastre/tools/make_demo_rasters.py project.gpkg

**Run this after ingest, not before.** The rasters are sized to cover the building
footprints, which are read from the `unit` table - and that table is only populated once
ingest has imported them.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import rasterio
import shapely.wkb
from rasterio.transform import from_origin
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sidecar"))


RES = 0.5
PAD = 25.0
GROUND = 912.4
STOREY = 3.0
PLINTH = 0.6


def footprints(conn: sqlite3.Connection) -> list:
    try:
        rows = conn.execute(
            "SELECT footprint_wkb FROM unit WHERE unit_type = 'building'").fetchall()
    except sqlite3.OperationalError as err:
        raise SystemExit(
            "no `unit` table yet - run ingest first. The rasters are sized to cover the "
            "footprints ingest imports, so there is nothing to cover until it has run."
        ) from err
    return [shapely.wkb.loads(r[0]) for r in rows]


def build(conn: sqlite3.Connection, out_dir: Path) -> tuple[Path, Path, dict]:
    shapes = footprints(conn)
    if not shapes:
        raise SystemExit("no building units in this project - run ingest first")

    x0, y0, x1, y1 = unary_union(shapes).bounds
    x0, y0, x1, y1 = x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD
    w, h = int((x1 - x0) / RES), int((y1 - y0) / RES)
    xs = x0 + (np.arange(w) + 0.5) * RES
    ys = y1 - (np.arange(h) + 0.5) * RES
    xx, yy = np.meshgrid(xs, ys)
    rng = np.random.default_rng(20260903)

    dem = np.full(xx.shape, GROUND) + rng.normal(0, 0.02, xx.shape)
    dsm = dem.copy()

    meta = {}
    for i, poly in enumerate(shapes):
        storeys = 4 + i % 4                       # 4-7 storeys, varied but deterministic
        slab = GROUND + PLINTH + storeys * STOREY
        mnx, mny, mxx, mxy = poly.bounds
        box = (xx >= mnx) & (xx <= mxx) & (yy >= mny) & (yy <= mxy)
        inside = np.zeros(xx.shape, bool)
        idx = np.argwhere(box)
        from shapely.geometry import Point
        for r, c in idx:                          # exact, and these grids are small
            if poly.covers(Point(xx[r, c], yy[r, c])):
                inside[r, c] = True
        dsm[inside] = slab + rng.normal(0, 0.02, int(inside.sum()))

        # a parapet ring and a rooftop tank, so the median estimator is exercised
        ring = inside & ~_erode(inside, int(0.8 / RES))
        dsm[ring] = slab + 1.0
        rr = idx[len(idx) // 2]
        dsm[rr[0]:rr[0] + 4, rr[1]:rr[1] + 4] = slab + 5.0
        meta[f"BLD-{i}"] = {"storeys": storeys, "slab_m": round(slab, 2)}

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, arr in (("demo_dem.tif", dem), ("demo_dsm.tif", dsm)):
        p = out_dir / name
        with rasterio.open(p, "w", driver="GTiff", height=h, width=w, count=1,
                           dtype="float32", crs="EPSG:32643",
                           transform=from_origin(x0, y1, RES, RES),
                           nodata=-9999.0, compress="deflate") as dst:
            dst.write(arr.astype("float32"), 1)
        paths.append(p)
    return paths[0], paths[1], meta


def _erode(mask: np.ndarray, k: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(max(k, 1)):
        out &= np.roll(out, 1, 0) & np.roll(out, -1, 0) & np.roll(out, 1, 1) & np.roll(out, -1, 1)
    return out


def register(conn: sqlite3.Connection, dem: Path, dsm: Path) -> None:
    """Record the rasters and their source in P2's tables, labelled synthetic."""
    conn.execute(
        "INSERT OR REPLACE INTO source (source_id, source_type, name, provider, "
        "capture_date, crs, vertical_datum, horizontal_accuracy_m, vertical_accuracy_m, "
        "coverage_wkt, processing_status) VALUES "
        "('SRC-SYNTH-ELEV','dsm','Synthetic elevation for the demo project',"
        "'generated - not a survey','2026-09-03','EPSG:32643','EGM2008',0.20,0.10,'',"
        "'accuracy_estimated')")
    for rid, kind, path in (("RST-DEM", "DEM", dem), ("RST-DSM", "DSM", dsm)):
        conn.execute(
            "INSERT OR REPLACE INTO raster (raster_id, kind, path, crs, vertical_datum, "
            "resolution_m, source_id) VALUES (?,?,?,?,?,?,?)",
            (rid, kind, str(path), "EPSG:32643", "EGM2008", RES, "SRC-SYNTH-ELEV"))
    conn.commit()


if __name__ == "__main__":
    gpkg = Path(sys.argv[1] if len(sys.argv) > 1 else "pilot.gpkg").resolve()
    conn = sqlite3.connect(gpkg)
    conn.row_factory = sqlite3.Row
    dem, dsm, meta = build(conn, gpkg.parent / "rasters")
    register(conn, dem, dsm)
    print(f"wrote {dem.name} and {dsm.name} to {dem.parent}")
    for k, v in meta.items():
        print(f"  {k}: {v['storeys']} storeys, slab at {v['slab_m']} m")
    print("registered as RST-DEM / RST-DSM against source SRC-SYNTH-ELEV")
