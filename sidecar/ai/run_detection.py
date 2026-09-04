"""
P3 AI Detection Engine CLI Orchestrator.
Runs building extraction & height/floor estimation pipeline on input rasters / arrays.
Supports YOLOv8-seg / ONNX local model inference & nDSM elevation fallback.
"""

import sys
import os
import json
import argparse
from typing import List, Dict, Any, Optional
import numpy as np
from rasterio.transform import Affine

# Ensure src directory is in Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai.models import SuggestionKind, FloorCountMethod
from ai.hybrid_pipeline import HybridP3Pipeline
from ai.ndsm_estimator import NDSMEstimator
from ai.footprint_extractor import FootprintExtractor
from ai.suggestion_builder import SuggestionBuilder


def process_ndsm_detection(
    ndsm_array: np.ndarray,
    dsm_array: np.ndarray,
    dem_array: np.ndarray,
    source_raster_ids: List[str],
    crs: str = "EPSG:32643",
    output_dir: Optional[str] = None,
    transform: Optional["Affine"] = None
) -> List[Dict[str, Any]]:
    """
    Execute AI detection pipeline on nDSM/DSM/DEM arrays.
    Returns list of contract-compliant AI Suggestion dictionaries.

    `transform` is the raster's affine transform and should always be supplied. Without
    it FootprintExtractor falls back to the identity transform, so the polygons come back
    in pixel indices while the contract states they are in the project CRS in metres.
    Both are plain numbers, so nothing downstream can tell them apart: P4 would place the
    building at (50, 50) in UTM 43N -- roughly 276 km from the parcel it belongs to, off
    the coast -- and its area filter would be out by the square of the pixel size.
    Caught by feeding a real DSM through this function and comparing the bounds against
    the footprint the same building has in the register.

    Elevation statistics are taken **per footprint**, not over the whole raster. Passing
    the full arrays gives every building in a scene the same ground level, roof level and
    storey count -- the tallest and the shortest come back identical. It happens to look
    right on a single-building tile, where the 90th percentile of the whole surface lands
    on the one roof present, which is exactly why it survived until a second building
    appeared.
    """
    extractor = FootprintExtractor()
    estimator = NDSMEstimator()
    builder = SuggestionBuilder()

    # Extract building footprint polygons
    polygons = extractor.extract_from_ndsm(ndsm_array, transform=transform)
    suggestions = []

    for i, poly in enumerate(polygons):
        # Calculate zonal elevation stats over this footprint alone
        stats = estimator.estimate_from_arrays(
            dsm_array, dem_array, mask=_footprint_mask(poly, dsm_array.shape, transform)
        )

        # Build AI Suggestion object
        suggestion = builder.create_suggestion(
            kind=SuggestionKind.BUILDING_OUTLINE,
            polygon=poly,
            source_raster_ids=source_raster_ids,
            crs=crs,
            confidence=stats["confidence"],
            floor_count=stats["floor_count"],
            floor_count_method=FloorCountMethod(stats["floor_count_method"]) if stats["floor_count_method"] else None,
            ground_level_m=stats["ground_level_m"],
            roof_level_m=stats["roof_level_m"]
        )

        suggestion_dict = suggestion.to_contract_dict()
        suggestions.append(suggestion_dict)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            out_file = os.path.join(output_dir, f"suggestion_{suggestion.suggestion_id}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(suggestion_dict, f, indent=2)

    return suggestions


def _footprint_mask(
    poly, shape: tuple, transform: Optional["Affine"]
) -> Optional[np.ndarray]:
    """Boolean mask selecting the cells this footprint covers.

    Returns None when there is no transform to relate the polygon to the grid, which
    keeps the previous whole-raster behaviour for a caller that has no georeferencing
    rather than masking against coordinates that do not mean anything.
    """
    if transform is None:
        return None
    from rasterio.features import geometry_mask

    return ~geometry_mask([poly], out_shape=shape, transform=transform, invert=False)


def process_hybrid_detection(
    ortho_image_bgr: Optional[np.ndarray],
    dsm_array: Optional[np.ndarray] = None,
    dem_array: Optional[np.ndarray] = None,
    model_path: Optional[str] = None,
    source_raster_ids: Optional[List[str]] = None,
    crs: str = "EPSG:32643",
    output_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Execute Hybrid YOLOv8 ONNX + Elevation Fallback pipeline.
    """
    pipeline = HybridP3Pipeline(model_path=model_path)
    suggestions = pipeline.process_ortho_and_elevation(
        ortho_image_bgr=ortho_image_bgr,
        dsm_array=dsm_array,
        dem_array=dem_array,
        source_raster_ids=source_raster_ids,
        crs=crs
    )

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for item in suggestions:
            out_file = os.path.join(output_dir, f"suggestion_{item['suggestion_id']}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(item, f, indent=2)

    return suggestions


def main():
    parser = argparse.ArgumentParser(description="P3 AI Detection Engine")
    parser.add_argument("--model-path", default=None, help="Path to local ONNX YOLOv8-seg weights file")
    parser.add_argument("--crs", default="EPSG:32643", help="Target projected CRS (default: EPSG:32643)")
    parser.add_argument("--output-dir", default="output", help="Output directory for JSON suggestions")
    args = parser.parse_args()

    print(f"[P3 Engine] Initialized YOLOv8 ONNX & Hybrid Pipeline | CRS: {args.crs}")
    if args.model_path:
        print(f"[P3 Engine] Loaded local ONNX model: {args.model_path}")
    print("[P3 Engine] Ready for raster detection pipeline processing.")


if __name__ == "__main__":
    main()
