"""
Unit test suite for P3 AI Detection Engine.
Verifies nDSM calculation, floor estimation, FR-03/FR-05 compliance, and contract JSON schema.
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
from run_detection import process_ndsm_detection


class TestP3AIDetection(unittest.TestCase):
    def setUp(self):
        self.estimator = NDSMEstimator(default_floor_height_m=3.0)
        self.extractor = FootprintExtractor(min_footprint_area_m2=10.0, simplify_tolerance_m=0.1)
        self.builder = SuggestionBuilder()

    def test_ndsm_floor_estimation(self):
        """Test nDSM height and floor count estimation logic."""
        # 10x10 synthetic raster with 9m building height (expected 3 floors)
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
        dsm = np.full((10, 10), 11.0, dtype=np.float32) # Only 1m height (below building threshold)

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
        ndsm[5:15, 5:15] = 6.0  # 10x10 building patch with 6m height

        polygons = self.extractor.extract_from_ndsm(ndsm)
        self.assertEqual(len(polygons), 1)
        self.assertIsInstance(polygons[0], Polygon)
        self.assertGreater(polygons[0].area, 50.0)

    def test_pipeline_execution(self):
        """Verify end-to-end pipeline execution in process_ndsm_detection."""
        dem = np.full((30, 30), 10.0, dtype=np.float32)
        dsm = np.full((30, 30), 10.0, dtype=np.float32)
        dsm[10:25, 10:25] = 22.0  # 15x15 building patch with 12m height (4 floors)
        ndsm = dsm - dem

        suggestions = process_ndsm_detection(
            ndsm_array=ndsm,
            dsm_array=dsm,
            dem_array=dem,
            source_raster_ids=["test_raster_dsm"],
            crs="EPSG:32643"
        )
        self.assertGreater(len(suggestions), 0)
        first = suggestions[0]
        self.assertEqual(first["kind"], "building_outline")
        self.assertEqual(first["crs"], "EPSG:32643")
        self.assertEqual(first["review"]["state"], "pending")
        self.assertEqual(first["attributes"]["floor_count"], 4)


if __name__ == "__main__":
    unittest.main()
