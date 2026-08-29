"""Zonal statistics over a footprint mask.

Two choices here are deliberate and should not be "simplified" later:

* **median** for ground level, not mean - resists vegetation and DEM edge artefacts
* **p90** for roof level, not max - max catches antennas, water tanks and lift machine
  rooms, inflating every building by 2-4 m
"""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry


def ground_level(dem_path: str, footprint: BaseGeometry) -> float:
    """Median DEM value inside the footprint."""
    raise NotImplementedError


def roof_level(dsm_path: str, footprint: BaseGeometry, percentile: float = 90.0) -> float:
    """High-percentile DSM value inside the footprint."""
    raise NotImplementedError


def sample(raster_path: str, footprint: BaseGeometry):
    """Masked 1-D array of raster values inside the footprint, nodata removed."""
    raise NotImplementedError
