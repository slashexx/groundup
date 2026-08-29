import os
import sys
import sqlite3
import unittest
import geopandas as gpd
from shapely.geometry import Polygon

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from run_pipeline import GeoDataPipeline
from src.pipeline.file_inspector import FileInspector
from src.pipeline.harmonizer import SpatialHarmonizer

class TestP2PipelineRobustness(unittest.TestCase):

    def setUp(self):
        self.gpkg_path = "output/robustness_test.gpkg"
        if os.path.exists(self.gpkg_path):
            os.remove(self.gpkg_path)

    def tearDown(self):
        if os.path.exists(self.gpkg_path):
            os.remove(self.gpkg_path)

    def test_01_invalid_file_handling(self):
        """Test that invalid file paths return clear error responses without crashing."""
        inspector = FileInspector()
        res = inspector.inspect("non_existent_file.geojson")
        self.assertFalse(res["valid"])
        self.assertIn("does not exist", res["error"])

        res_unsupported = inspector.inspect("tests/test_p2_pipeline.py")
        self.assertFalse(res_unsupported["valid"])
        self.assertIn("Unsupported file extension", res_unsupported["error"])

    def test_02_geometry_repair_make_valid(self):
        """Test that self-intersecting ('bowtie') polygons are automatically repaired into valid geometries."""
        # Bowtie self-intersecting polygon
        bowtie_poly = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        self.assertFalse(bowtie_poly.is_valid)

        gdf = gpd.GeoDataFrame({"parcel_local_id": ["P_INVALID_1"], "geometry": [bowtie_poly]}, crs="EPSG:4326")
        harmonizer = SpatialHarmonizer(target_crs="EPSG:32643")
        
        harmonized_gdf = harmonizer.harmonize_vector(gdf)
        self.assertTrue(harmonized_gdf.geometry.iloc[0].is_valid)
        self.assertEqual(harmonized_gdf.crs.to_string(), "EPSG:32643")

    def test_03_missing_crs_fallback(self):
        """Test that datasets missing CRS tags are safely assigned fallback CRS and reprojected."""
        poly = Polygon([(72.8, 19.0), (72.9, 19.0), (72.9, 19.1), (72.8, 19.1), (72.8, 19.0)])
        gdf_no_crs = gpd.GeoDataFrame({"parcel_local_id": ["P_NO_CRS"]}, geometry=[poly])
        self.assertIsNone(gdf_no_crs.crs)

        harmonizer = SpatialHarmonizer(target_crs="EPSG:32643")
        harmonized = harmonizer.harmonize_vector(gdf_no_crs, default_source_crs="EPSG:4326")
        self.assertEqual(harmonized.crs.to_string(), "EPSG:32643")

    def test_04_sequential_layer_appends(self):
        """Test that multiple files can be processed sequentially into the same GeoPackage without table corruption."""
        pipeline = GeoDataPipeline(gpkg_output_path=self.gpkg_path, target_crs="EPSG:32643")
        pipeline.setup_project()

        # Import File 1
        res1 = pipeline.process_file(
            input_file_path="test_data/sample_parcels.geojson",
            layer_name="parcel",
            source_id="SRC_SET_01",
            source_type="parcel_map"
        )
        self.assertTrue(res1)

        # Import File 2 (Appends layer building_footprint)
        res2 = pipeline.process_file(
            input_file_path="test_data/sample_buildings.geojson",
            layer_name="building_footprint",
            source_id="SRC_SET_02",
            source_type="footprint"
        )
        self.assertTrue(res2)

        # Verify source table has both records
        conn = sqlite3.connect(self.gpkg_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM source;")
        count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(count, 2)

    def test_05_column_mapping(self):
        """Test column renaming utility to align custom surveyor attribute names to contract specifications."""
        pipeline = GeoDataPipeline(gpkg_output_path=self.gpkg_path, target_crs="EPSG:32643")
        pipeline.setup_project()

        column_mapping = {
          "parcel_id": "parcel_local_id",
          "survey_no": "parent_ulpin_14"
        }

        res = pipeline.process_file(
            input_file_path="test_data/sample_parcels.geojson",
            layer_name="parcel",
            source_id="SRC_MAPPED_01",
            source_type="parcel_map",
            column_mapping=column_mapping
        )
        self.assertTrue(res)

        gdf = gpd.read_file(self.gpkg_path, layer="parcel")
        self.assertIn("parcel_local_id", gdf.columns)

if __name__ == "__main__":
    unittest.main()
