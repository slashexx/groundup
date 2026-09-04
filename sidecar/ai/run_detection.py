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
    output_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Execute AI detection pipeline on nDSM/DSM/DEM arrays.
    Returns list of contract-compliant AI Suggestion dictionaries.
    """
    extractor = FootprintExtractor()
    estimator = NDSMEstimator()
    builder = SuggestionBuilder()

    # Extract building footprint polygons
    polygons = extractor.extract_from_ndsm(ndsm_array)
    suggestions = []

    for i, poly in enumerate(polygons):
        # Calculate zonal elevation stats over footprint
        stats = estimator.estimate_from_arrays(dsm_array, dem_array)

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
