#!/usr/bin/env python3
"""Generate synthetic DEM/DSM rasters for the demo site.

Real pilot data is not chosen yet, and waiting for it would block the extrusion work.
These rasters carry *known planted values*, which makes them better than real data for
testing the algorithm: we can assert that zonal statistics recover exactly the heights we
put in, and that the specific estimator choices are the ones that survive.

Three artefacts are planted deliberately, each targeting one design decision:

  vegetation spikes near the footprint edge   -> why ground uses median, not mean
  a rooftop water tank at +5 m                -> why roof uses p90, not max
  a 0.6 m parapet ring 1 m above the slab     -> why parapet_deduction exists

Output is git-ignored; regenerate with:

    ./.venv/bin/python sidecar/cadastre/tools/make_rasters.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/synthetic"

CRS = "EPSG:32643"
RES = 0.25
E, N = 445000.0, 1434000.0

# Site window, generous enough to contain the utility corridor
X0, X1 = E - 10, E + 90
Y0, Y1 = N - 5, N + 35

GROUND = 912.4          # true bare-earth level
ROOF_SLAB = 934.0       # true top of the highest floor slab
PARAPET_TOP = 935.0     # what a DSM actually sees around the roof edge
TANK_TOP = 940.0        # rooftop water tank - the thing `max` would latch onto

BLD = (E + 8, N + 6, E + 32, N + 24)      # matches the fixture building footprint
PARAPET_W = 0.6                            # ~11% of roof area, so p90 lands on it
TANK = (E + 12, N + 10, E + 14, N + 12)   # 2 x 2 m


def _grid():
    w = round((X1 - X0) / RES)
    h = round((Y1 - Y0) / RES)
    xs = X0 + (np.arange(w) + 0.5) * RES
    ys = Y1 - (np.arange(h) + 0.5) * RES
    return np.meshgrid(xs, ys)


def _inside(xx, yy, box, inset=0.0):
    x0, y0, x1, y1 = box
    return ((xx >= x0 + inset) & (xx <= x1 - inset)
            & (yy >= y0 + inset) & (yy <= y1 - inset))


def build() -> tuple[np.ndarray, np.ndarray]:
    xx, yy = _grid()
    rng = np.random.default_rng(20260829)

    # --- DEM: bare earth, symmetric sensor noise plus one-sided vegetation returns ---
    dem = np.full(xx.shape, GROUND) + rng.normal(0, 0.02, xx.shape)
    # Shrubs misclassified as ground around the building, plus interpolation artefacts
    # under it (a DEM has no real observations beneath a roof). Both skew the MEAN
    # upward and leave the MEDIAN untouched - which is the whole argument for median.
    near_edge = _inside(xx, yy, BLD, inset=-3.0) & ~_inside(xx, yy, BLD, inset=-0.5)
    veg = near_edge & (rng.random(xx.shape) < 0.18)
    dem[veg] += rng.uniform(1.5, 4.0, int(veg.sum()))
    artefact = _inside(xx, yy, BLD) & (rng.random(xx.shape) < 0.12)
    dem[artefact] += rng.uniform(0.8, 2.5, int(artefact.sum()))

    # --- DSM: ground everywhere, then the building on top -------------------------
    dsm = dem.copy()
    roof = _inside(xx, yy, BLD)
    dsm[roof] = ROOF_SLAB + rng.normal(0, 0.02, int(roof.sum()))

    parapet = roof & ~_inside(xx, yy, BLD, inset=PARAPET_W)
    dsm[parapet] = PARAPET_TOP + rng.normal(0, 0.02, int(parapet.sum()))

    tank = _inside(xx, yy, TANK)
    dsm[tank] = TANK_TOP

    return dem.astype("float32"), dsm.astype("float32")


def write(name: str, arr: np.ndarray) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
        count=1, dtype="float32", crs=CRS, transform=from_origin(X0, Y1, RES, RES),
        nodata=-9999.0, compress="deflate",
    ) as dst:
        dst.write(arr, 1)
    return path


if __name__ == "__main__":
    dem, dsm = build()
    for name, arr in (("dem.tif", dem), ("dsm.tif", dsm)):
        p = write(name, arr)
        print(f"wrote {p.relative_to(REPO)}  {arr.shape[1]}x{arr.shape[0]} @ {RES} m")

    xx, yy = _grid()
    roof = _inside(xx, yy, BLD)
    par = roof & ~_inside(xx, yy, BLD, inset=PARAPET_W)
    print(f"\nplanted   ground {GROUND}  slab {ROOF_SLAB}  parapet {PARAPET_TOP}  tank {TANK_TOP}")
    print(f"parapet   {100 * par.sum() / roof.sum():.1f}% of roof area "
          f"(needs >10% for p90 to land on it)")
    print(f"roof   mean {dsm[roof].mean():7.2f}  median {np.median(dsm[roof]):7.2f}"
          f"  p90 {np.percentile(dsm[roof], 90):7.2f}  max {dsm[roof].max():7.2f}")
    print(f"ground mean {dem[roof].mean():7.2f}  median {np.median(dem[roof]):7.2f}"
          f"  p90 {np.percentile(dem[roof], 90):7.2f}  max {dem[roof].max():7.2f}")
    print(f"truth       slab {ROOF_SLAB}   ground {GROUND}   <- median recovers both")
