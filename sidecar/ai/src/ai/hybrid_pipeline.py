"""
Hybrid P3 AI Detection Pipeline.
Combines YOLOv8-seg / ONNX orthophoto building segmentation with DSM-DEM nDSM height estimation fallback.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from shapely.geometry import Polygon
from rasterio.transform import Affine

from .models import SuggestionKind, FloorCountMethod
from .yolo_detector import YOLOv8ONNXDetector
from .ndsm_estimator import NDSMEstimator
from .footprint_extractor import FootprintExtractor
from .suggestion_builder import SuggestionBuilder


class HybridP3Pipeline:
    def __init__(
        self,
        model_path: Optional[str] = None,
        default_floor_height_m: float = 3.0
    ):
        self.yolo_detector = YOLOv8ONNXDetector(model_path=model_path)
        self.ndsm_estimator = NDSMEstimator(default_floor_height_m=default_floor_height_m)
        self.footprint_extractor = FootprintExtractor()
        self.suggestion_builder = SuggestionBuilder(
            model_name="yolov8s-seg-buildings",
            model_version="1.0.0"
        )

    def process_ortho_and_elevation(
        self,
        ortho_image_bgr: Optional[np.ndarray],
        dsm_array: Optional[np.ndarray] = None,
        dem_array: Optional[np.ndarray] = None,
        source_raster_ids: Optional[List[str]] = None,
        transform: Optional[Affine] = None,
        crs: str = "EPSG:32643"
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid detection pipeline.
        
        1. 2D Outline Extraction: Uses YOLOv8 ONNX on orthophoto, or nDSM thresholding fallback.
        2. 3D Height Estimation: Uses NDSMEstimator over detected outlines if DSM/DEM present.
        3. Contract Emission: Emits validated JSON matching p3-suggestion.schema.json.
        """
        if source_raster_ids is None:
            source_raster_ids = ["ortho_raster_001"]

        detected_polygons: List[Tuple[Polygon, float]] = []

        # 1. Primary 2D Building Outline Detection from RGB Orthophoto
        if ortho_image_bgr is not None:
            detected_polygons = self.yolo_detector.detect_building_polygons(
                ortho_image_bgr, transform=transform
            )

        # Fallback: If no orthophoto provided, extract from nDSM elevation raster
        if not detected_polygons and dsm_array is not None and dem_array is not None:
            ndsm = self.ndsm_estimator.compute_ndsm(dsm_array, dem_array)
            extracted_polys = self.footprint_extractor.extract_from_ndsm(ndsm, transform=transform)
            detected_polygons = [(p, 0.80) for p in extracted_polys]

        suggestions = []
        for poly, detection_conf in detected_polygons:
            # 2. 3D Elevation & Floor Count Estimation
            if dsm_array is not None and dem_array is not None:
                stats = self.ndsm_estimator.estimate_from_arrays(dsm_array, dem_array)
                ground_m = stats["ground_level_m"]
                roof_m = stats["roof_level_m"]
                floors = stats["floor_count"]
                method = FloorCountMethod(stats["floor_count_method"]) if stats["floor_count_method"] else None
                final_conf = round((detection_conf + stats["confidence"]) / 2.0, 2)
            else:
                # FR-03 Compliance: Fallback when elevation data is absent
                ground_m = None
                roof_m = None
                floors = None
                method = None
                final_conf = detection_conf

            # 3. Create Validated AI Suggestion (FR-05 review.state = "pending")
            suggestion = self.suggestion_builder.create_suggestion(
                kind=SuggestionKind.BUILDING_OUTLINE,
                polygon=poly,
                source_raster_ids=source_raster_ids,
                crs=crs,
                confidence=final_conf,
                floor_count=floors,
                floor_count_method=method,
                ground_level_m=ground_m,
                roof_level_m=roof_m
            )

            suggestions.append(suggestion.to_contract_dict())

        return suggestions
