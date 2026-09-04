"""
Unit test suite for P3 AI Detection Engine.
Verifies nDSM calculation, YOLOv8 ONNX segmentation, hybrid pipeline, FR-03/FR-05 compliance, robust edge cases, and contract JSON schema.
"""

import sys
import os
import unittest
import numpy as np
from shapely.geometry import Polygon

# Dynamically resolve paths for sidecar/ai
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "src"))

from ai.models import (
    AISuggestion,
    SuggestionKind,
    ReviewStateEnum,
    FloorCountMethod
)
from ai.ndsm_estimator import NDSMEstimator
from ai.footprint_extractor import FootprintExtractor
from ai.suggestion_builder import SuggestionBuilder
from ai.yolo_detector import YOLOv8ONNXDetector
from ai.hybrid_pipeline import HybridP3Pipeline
from run_detection import process_ndsm_detection, process_hybrid_detection


class TestP3AIDetection(unittest.TestCase):
    def setUp(self):
        self.estimator = NDSMEstimator(default_floor_height_m=3.0)
        self.extractor = FootprintExtractor(min_footprint_area_m2=10.0, simplify_tolerance_m=0.1)
        self.builder = SuggestionBuilder()
        self.yolo_detector = YOLOv8ONNXDetector()

    def test_ndsm_floor_estimation(self):
        """Test nDSM height and floor count estimation logic."""
        dem = np.full((10, 10), 10.0, dtype=np.float32)
        dsm = np.full((10, 10), 19.0, dtype=np.float32)

        stats = self.estimator.estimate_from_arrays(dsm, dem)
        self.assertEqual(stats["floor_count"], 3)
        self.assertEqual(stats["height_m"], 9.0)
        self.assertEqual(stats["floor_count_method"], "ndsm_division")
        self.assertGreaterEqual(stats["confidence"], 0.40)

    def test_fr03_missing_data_compliance(self):
        """FR-03: Missing or low elevation data must return floor_count=None and confidence=0.0."""
        dem = np.full((10, 10), 10.0, dtype=np.float32)
        dsm = np.full((10, 10), 11.0, dtype=np.float32)

        stats = self.estimator.estimate_from_arrays(dsm, dem)
        self.assertIsNone(stats["floor_count"])
        self.assertIsNone(stats["floor_count_method"])
        self.assertEqual(stats["confidence"], 0.0)

    def test_fr05_pending_review_state(self):
        """FR-05: Outbound suggestions must strictly default to review.state = 'pending'."""
        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        suggestion = self.builder.create_suggestion(
            kind=SuggestionKind.BUILDING_OUTLINE,
            polygon=poly,
            source_raster_ids=["dsm_ortho_001"],
            crs="EPSG:32643",
            confidence=0.85,
            floor_count=2
        )
        self.assertEqual(suggestion.review.state, ReviewStateEnum.PENDING)

    def test_contract_schema_validation(self):
        """Verify suggestion dictionary passes p3-suggestion.schema.json validation."""
        poly = Polygon([(500000, 3000000), (500020, 3000000), (500020, 3000020), (500000, 3000020), (500000, 3000000)])
        suggestion = self.builder.create_suggestion(
            kind=SuggestionKind.BUILDING_OUTLINE,
            polygon=poly,
            source_raster_ids=["dsm_raster_001"],
            crs="EPSG:32643",
            confidence=0.88,
            floor_count=4,
            floor_count_method=FloorCountMethod.NDSM_DIVISION,
            ground_level_m=12.5,
            roof_level_m=24.5
        )

        suggestion_dict = suggestion.to_contract_dict()
        is_valid = self.builder.validate_dict(suggestion_dict)
        self.assertTrue(is_valid)

    def test_footprint_extraction(self):
        """Verify vector building polygon extraction from nDSM raster mask."""
        ndsm = np.zeros((20, 20), dtype=np.float32)
        ndsm[5:15, 5:15] = 6.0

        polygons = self.extractor.extract_from_ndsm(ndsm)
        self.assertEqual(len(polygons), 1)
        self.assertIsInstance(polygons[0], Polygon)
        self.assertGreater(polygons[0].area, 50.0)

    def test_yolo_onnx_segmentation(self):
        """Test YOLOv8 ONNX building polygon segmentation from RGB synthetic orthophoto."""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[20:80, 20:80] = 255  # Synthetic bright building square

        results = self.yolo_detector.detect_building_polygons(rgb)
        self.assertGreater(len(results), 0)
        poly, conf = results[0]
        self.assertIsInstance(poly, Polygon)
        self.assertGreater(conf, 0.50)

    def test_hybrid_pipeline(self):
        """Test Hybrid Orthophoto + Elevation Pipeline processing."""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[20:80, 20:80] = 255

        dem = np.full((100, 100), 10.0, dtype=np.float32)
        dsm = np.full((100, 100), 10.0, dtype=np.float32)
        dsm[20:80, 20:80] = 22.0  # 12m height (4 floors)

        pipeline = HybridP3Pipeline()
        suggestions = pipeline.process_ortho_and_elevation(
            ortho_image_bgr=rgb,
            dsm_array=dsm,
            dem_array=dem,
            source_raster_ids=["ortho_dsm_composite"],
            crs="EPSG:32643"
        )
        self.assertGreater(len(suggestions), 0)
        first = suggestions[0]
        self.assertEqual(first["kind"], "building_outline")
        self.assertEqual(first["review"]["state"], "pending")
        self.assertEqual(first["attributes"]["floor_count"], 4)
        self.assertEqual(first["attributes"]["floor_count_method"], "ndsm_division")

    def test_hybrid_elevation_fallback(self):
        """FR-03 Fallback: When orthophoto is present but elevation is absent, floor_count = None."""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[20:80, 20:80] = 255

        pipeline = HybridP3Pipeline()
        suggestions = pipeline.process_ortho_and_elevation(
            ortho_image_bgr=rgb,
            dsm_array=None,
            dem_array=None,
            source_raster_ids=["ortho_only_001"]
        )
        self.assertGreater(len(suggestions), 0)
        first = suggestions[0]
        self.assertIsNone(first["attributes"].get("floor_count"))
        self.assertEqual(first["review"]["state"], "pending")

    def test_edge_case_nan_inf_nodata_pixels(self):
        """Edge Case 1: Handles NaN, Inf, and NoData void values in elevation rasters cleanly."""
        dem = np.full((20, 20), 10.0, dtype=np.float32)
        dsm = np.full((20, 20), 22.0, dtype=np.float32)
        # Inject NaNs, Infs, and NoData void values
        dsm[0, 0] = np.nan
        dsm[0, 1] = np.inf
        dem[0, 2] = -9999.0

        stats = self.estimator.estimate_from_arrays(dsm, dem)
        self.assertEqual(stats["floor_count"], 4)
        self.assertIsNotNone(stats["ground_level_m"])

    def test_edge_case_empty_or_zero_arrays(self):
        """Edge Case 2: Blank or completely empty arrays return empty suggestions without crashing."""
        empty_ndsm = np.zeros((10, 10), dtype=np.float32)
        polys = self.extractor.extract_from_ndsm(empty_ndsm)
        self.assertEqual(len(polys), 0)

        empty_stats = self.estimator.estimate_from_arrays(None, None)
        self.assertIsNone(empty_stats["floor_count"])
        self.assertEqual(empty_stats["confidence"], 0.0)

    def test_edge_case_noise_area_filtering(self):
        """Edge Case 3: Filters small sub-threshold pixel noise blobs (< 10m²)."""
        ndsm = np.zeros((50, 50), dtype=np.float32)
        ndsm[5:7, 5:7] = 5.0  # Only 4 pixels (4m² < 10m² min threshold)

        polys = self.extractor.extract_from_ndsm(ndsm)
        self.assertEqual(len(polys), 0)

    def test_edge_case_antenna_spike_filtering(self):
        """Edge Case 4: 90th percentile filtering removes extreme single-pixel antenna spikes."""
        dem = np.full((20, 20), 10.0, dtype=np.float32)
        dsm = np.full((20, 20), 19.0, dtype=np.float32)  # 9m roof height (3 floors)
        dsm[5, 5] = 150.0  # Sensor error / 150m antenna spike on single pixel

        stats = self.estimator.estimate_from_arrays(dsm, dem)
        # Should calculate height ~9m (3 floors), NOT 140m (46 floors)
        self.assertEqual(stats["floor_count"], 3)


if __name__ == "__main__":
    unittest.main()
