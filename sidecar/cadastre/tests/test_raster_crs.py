"""A raster in a different CRS from the project.

This is the path that produced a confident wrong number: `rio_mask` does not reproject,
so a footprint in UTM metres against a DEM in degrees either missed the raster entirely
(reported as "no raster registered", the opposite of the truth) or clipped a few pixels
whose median became the building's roof.
"""
from __future__ import annotations

import numpy as np
import pytest
import rasterio
from cadastre.extrude import raster
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box
from shapely.ops import transform as shp_transform

UTM = "EPSG:32643"
E, N = 445000.0, 1434000.0
FOOTPRINT = box(E + 10, N + 10, E + 30, N + 30)      # 400 m2, in the project CRS


def _wgs84_raster(tmp_path, value=100.0):
    """The same ground, written in degrees instead of metres."""
    to_wgs = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    area = shp_transform(to_wgs.transform, box(E - 50, N - 50, E + 80, N + 80))
    x0, y0, x1, y1 = area.bounds
    w = h = 400
    res_x, res_y = (x1 - x0) / w, (y1 - y0) / h
    path = tmp_path / "dem_wgs84.tif"
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1,
                       dtype="float32", crs="EPSG:4326",
                       transform=from_origin(x0, y1, res_x, res_y)) as dst:
        dst.write(np.full((h, w), value, "float32"), 1)
    return str(path)


def test_a_raster_in_another_crs_is_reprojected_not_assumed(tmp_path):
    """A DEM in degrees over a project in metres reads correctly."""
    dem = _wgs84_raster(tmp_path, value=912.4)
    assert raster.ground_level(dem, FOOTPRINT, UTM) == pytest.approx(912.4, abs=0.01)


def test_coverage_of_a_reprojected_raster_is_a_real_fraction(tmp_path):
    """Not 1.0 from three pixels, and not 0.0 from a units mismatch.

    `expected` used to divide a project-CRS area by a raster-CRS cell size - metres by
    degrees - coming out about 1e10 too large, so any handful of valid pixels reported as
    full coverage and the gate that exists to catch thin data let them through.
    """
    dem = _wgs84_raster(tmp_path)
    assert raster.coverage(dem, FOOTPRINT, UTM) == pytest.approx(1.0, abs=0.05)


def test_without_being_told_the_crs_the_footprint_misses_the_raster(tmp_path):
    """The old behaviour, pinned so it cannot come back unnoticed."""
    dem = _wgs84_raster(tmp_path)
    assert raster.coverage(dem, FOOTPRINT) == 0.0
    with pytest.raises(raster.NoCoverage):
        raster.ground_level(dem, FOOTPRINT)


def test_a_footprint_outside_a_matching_raster_is_still_no_coverage(tmp_path):
    """Reprojection must not turn "somewhere else entirely" into a reading."""
    path = tmp_path / "far.tif"
    with rasterio.open(path, "w", driver="GTiff", height=50, width=50, count=1,
                       dtype="float32", crs=UTM,
                       transform=from_origin(E + 5000, N + 5000, 1.0, 1.0)) as dst:
        dst.write(np.full((50, 50), 5.0, "float32"), 1)
    assert raster.coverage(str(path), FOOTPRINT, UTM) == 0.0
