"""
Building Footprint Extraction Engine.
Extracts vector building polygons from elevation raster threshold masks or nDSM arrays.
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely import make_valid
from rasterio.transform import Affine
from rasterio.features import shapes


class FootprintExtractor:
    def __init__(
        self,
        min_building_height_m: float = 2.5,
        min_footprint_area_m2: float = 15.0,
        simplify_tolerance_m: float = 0.5
    ):
        self.min_building_height_m = min_building_height_m
        self.min_footprint_area_m2 = min_footprint_area_m2
        self.simplify_tolerance_m = simplify_tolerance_m

    def extract_from_ndsm(
        self,
        ndsm_array: np.ndarray,
        transform: Optional[Affine] = None
    ) -> List[Polygon]:
        """
        Extract building footprints from nDSM array by thresholding and vectorizing.
        """
        if ndsm_array is None or ndsm_array.size == 0:
            return []

        # Create binary building mask
        mask = (ndsm_array >= self.min_building_height_m).astype(np.uint8)

        if not np.any(mask):
            return []

        # Default transform if not provided (1m cell size)
        if transform is None:
            transform = Affine.identity()

        # Vectorize mask using rasterio features
        polygons = []
        for geom_dict, val in shapes(mask, mask=(mask == 1), transform=transform):
            if val == 1:
                poly = shape(geom_dict)
                poly = make_valid(poly)

                if isinstance(poly, MultiPolygon):
                    for sub_p in poly.geoms:
                        if sub_p.area >= self.min_footprint_area_m2:
                            polygons.append(sub_p)
                elif isinstance(poly, Polygon):
                    if poly.area >= self.min_footprint_area_m2:
                        polygons.append(poly)

        # Simplify building outlines to eliminate pixel jaggedness
        simplified_polygons = []
        for poly in polygons:
            simp = poly.simplify(self.simplify_tolerance_m, preserve_topology=True)
            simp = make_valid(simp)
            if isinstance(simp, Polygon) and simp.area >= self.min_footprint_area_m2:
                simplified_polygons.append(simp)

        return simplified_polygons
