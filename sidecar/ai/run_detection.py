"""
P3 AI Detection Engine CLI Orchestrator.
Runs building extraction & height/floor estimation pipeline on input rasters / arrays.
"""

import sys
import os
import json
import argparse
from typing import List, Dict, Any, Optional
import numpy as np
from shapely.geometry import Polygon

# Ensure src directory is in Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai.models import SuggestionKind, FloorCountMethod
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


def main():
    parser = argparse.ArgumentParser(description="P3 AI Detection Engine")
    parser.add_argument("--crs", default="EPSG:32643", help="Target projected CRS (default: EPSG:32643)")
    parser.add_argument("--output-dir", default="output", help="Output directory for JSON suggestions")
    args = parser.parse_args()

    print(f"[P3 Engine] Initialized AI Detection Engine | CRS: {args.crs}")
    print("[P3 Engine] Ready for raster detection pipeline processing.")


if __name__ == "__main__":
    main()
