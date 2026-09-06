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
from pyproj import Transformer
from rasterio.mask import mask as rio_mask
from shapely.ops import transform as shapely_transform
from shapely.geometry.base import BaseGeometry


class NoCoverage(ValueError):
    """The footprint has no valid raster pixels under it.

    Raised rather than returned as a default, because FR-03 forbids inventing a value
    for missing data. The caller must record the height as unknown.
    """


def _masked(raster_path: str | Path, footprint: BaseGeometry,
            footprint_crs: str | None = None):
    """Masked read, in the raster's own frame, translating rasterio's error into ours.

    `rio_mask` does not reproject: it assumes the shape is already in the raster's CRS.
    Nothing checked that. A project in UTM metres against a DEM in degrees produced one
    of two outcomes, both silent - either the shapes were disjoint and every building was
    reported as `skipped_no_raster` ("no raster registered for this footprint", the
    opposite of the truth), or they partially overlapped and the median of a handful of
    pixels became a building's roof level. A number, confidently wrong.

    So the footprint is reprojected into the raster's frame rather than assumed to be in
    it. A DEM in any CRS now works, which is what a registry that accepts a file from
    anyone requires.

    Returns the array, the pixel size, and the footprint *as sampled* - callers computing
    an expected pixel count need its area in the raster's units, not the project's.
    """
    with rasterio.open(raster_path) as src:
        shape = footprint
        if footprint_crs and src.crs and str(src.crs) != str(footprint_crs):
            try:
                shape = shapely_transform(
                    Transformer.from_crs(footprint_crs, src.crs, always_xy=True).transform,
                    footprint)
            except Exception as exc:                       # unknown or unusable CRS
                raise NoCoverage(
                    f"cannot compare a footprint in {footprint_crs} with {raster_path} "
                    f"in {src.crs}: {exc}") from exc
        try:
            arr, _ = rio_mask(src, [shape.__geo_interface__], crop=True, filled=False)
        except ValueError as exc:
            if "do not overlap" in str(exc):
                raise NoCoverage(f"footprint lies outside {raster_path}") from exc
            raise
        return arr, abs(src.transform.a), abs(src.transform.e), shape


def sample(raster_path: str | Path, footprint: BaseGeometry,
           footprint_crs: str | None = None) -> np.ndarray:
    """Valid raster values inside `footprint`, nodata removed, as a flat array."""
    arr, _, _, _ = _masked(raster_path, footprint, footprint_crs)
    values = np.ma.getdata(arr)[~np.ma.getmaskarray(arr)]
    if values.size == 0:
        raise NoCoverage(f"no valid pixels under footprint in {raster_path}")
    return values.astype("float64")


def ground_level(dem_path: str | Path, footprint: BaseGeometry,
                 footprint_crs: str | None = None) -> float:
    """Bare-earth level under a footprint.

    A DEM has no real observations beneath a roof, so values there are interpolated and
    carry artefacts. The median ignores them; the mean does not.
    """
    return float(np.median(sample(dem_path, footprint, footprint_crs)))


def roof_level(dsm_path: str | Path, footprint: BaseGeometry,
               footprint_crs: str | None = None) -> float:
    """Dominant roof plane - the top of the highest floor slab.

    See the module docstring for why this is a median and not a high percentile.
    """
    return float(np.median(sample(dsm_path, footprint, footprint_crs)))


def valid_pixels(raster_path: str | Path, footprint: BaseGeometry,
                 footprint_crs: str | None = None) -> int:
    """How many valid cells actually sit under the footprint.

    A fraction cannot express "this raster is too coarse for this building". A 20 m2
    footprint on a 5 m DEM covers well under one cell, so a single valid pixel is 100%
    coverage - and the median of one number is that number, published as a measured roof
    level with nothing marking it as a sample of one.
    """
    try:
        arr, _, _, _ = _masked(raster_path, footprint, footprint_crs)
    except NoCoverage:
        return 0
    return int((~np.ma.getmaskarray(arr)).sum())


def coverage(raster_path: str | Path, footprint: BaseGeometry,
             footprint_crs: str | None = None) -> float:
    """Fraction of the footprint with valid data, 0.0-1.0.

    Callers should refuse to derive heights from thin coverage rather than quietly
    averaging a handful of pixels.

    The expected pixel count is computed from the footprint *as sampled*, in the raster's
    own units. Dividing a project-CRS area by a raster-CRS cell size mixed metres with
    degrees in one expression: `expected` came out around 1e10 times too large, so three
    valid pixels reported as full coverage and the gate this function exists to feed let
    them through.
    """
    try:
        arr, res_x, res_y, sampled = _masked(raster_path, footprint, footprint_crs)
    except NoCoverage:
        return 0.0                      # entirely outside the raster is zero coverage
    valid = int((~np.ma.getmaskarray(arr)).sum())
    expected = sampled.area / (res_x * res_y)
    return min(1.0, valid / expected) if expected else 0.0
