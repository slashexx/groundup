"""Zonal statistics over a footprint mask.

**Both ground and roof use the median**, and that is the whole design.

The obvious choices are wrong in ways that are easy to miss:

    estimator   DSM over the demo roof   DEM under it
    mean                  +0.15 m              +0.20 m     dragged by outliers
    p90                   +0.97 m              +1.09 m     lands on the parapet
    max                   +6.00 m              +2.52 m     lands on the water tank
    median                 0.00 m               0.00 m

A DSM over a flat roof is bimodal: a large slab plane and a small parapet ring, plus
point features like water tanks, lift machine rooms and antennas. The slab is always the
dominant area for any real building, so the median finds it and rejects everything else
regardless of building size. A percentile cannot do that - the parapet's share of roof
area depends on the building's dimensions, so the correct percentile is different for
every structure.

This is also why there is no parapet deduction. An earlier design took a high percentile
and subtracted a constant; the median removes both the constant and the fragility.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry.base import BaseGeometry


class NoCoverage(ValueError):
    """The footprint has no valid raster pixels under it.

    Raised rather than returned as a default, because FR-03 forbids inventing a value
    for missing data. The caller must record the height as unknown.
    """


def _masked(raster_path: str | Path, footprint: BaseGeometry):
    """Masked read, translating rasterio's disjoint-shape error into our own.

    Callers should not have to know rasterio's exception types to distinguish "no data
    here" from a genuine I/O failure.
    """
    with rasterio.open(raster_path) as src:
        try:
            arr, _ = rio_mask(src, [footprint.__geo_interface__], crop=True, filled=False)
        except ValueError as exc:
            if "do not overlap" in str(exc):
                raise NoCoverage(f"footprint lies outside {raster_path}") from exc
            raise
        return arr, abs(src.transform.a), abs(src.transform.e)


def sample(raster_path: str | Path, footprint: BaseGeometry) -> np.ndarray:
    """Valid raster values inside `footprint`, nodata removed, as a flat array."""
    arr, _, _ = _masked(raster_path, footprint)
    values = np.ma.getdata(arr)[~np.ma.getmaskarray(arr)]
    if values.size == 0:
        raise NoCoverage(f"no valid pixels under footprint in {raster_path}")
    return values.astype("float64")


def ground_level(dem_path: str | Path, footprint: BaseGeometry) -> float:
    """Bare-earth level under a footprint.

    A DEM has no real observations beneath a roof, so values there are interpolated and
    carry artefacts. The median ignores them; the mean does not.
    """
    return float(np.median(sample(dem_path, footprint)))


def roof_level(dsm_path: str | Path, footprint: BaseGeometry) -> float:
    """Dominant roof plane - the top of the highest floor slab.

    See the module docstring for why this is a median and not a high percentile.
    """
    return float(np.median(sample(dsm_path, footprint)))


def coverage(raster_path: str | Path, footprint: BaseGeometry) -> float:
    """Fraction of the footprint with valid data, 0.0-1.0.

    Callers should refuse to derive heights from thin coverage rather than quietly
    averaging a handful of pixels.
    """
    try:
        arr, res_x, res_y = _masked(raster_path, footprint)
    except NoCoverage:
        return 0.0                      # entirely outside the raster is zero coverage
    valid = int((~np.ma.getmaskarray(arr)).sum())
    expected = footprint.area / (res_x * res_y)
    return min(1.0, valid / expected) if expected else 0.0
