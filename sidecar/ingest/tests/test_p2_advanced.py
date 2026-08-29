import os
import sys
import sqlite3
import unittest
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from run_pipeline import GeoDataPipeline
from src.pipeline.file_inspector import FileInspector
from src.pipeline.harmonizer import SpatialHarmonizer
from src.pipeline.gpkg_writer import GeoPackageWriter

class TestP2AdvancedPipeline(unittest.TestCase):

    def setUp(self):
        self.gpkg_path = "output/advanced_test.gpkg"
        if os.path.exists(self.gpkg_path):
            os.remove(self.gpkg_path)

    def tearDown(self):
        if os.path.exists(self.gpkg_path):
            os.remove(self.gpkg_path)

    def test_01_empty_geodataframe_handling(self):
        """Test that writing an empty GeoDataFrame fails gracefully without throwing an exception."""
        writer = GeoPackageWriter(self.gpkg_path)
        empty_gdf = gpd.GeoDataFrame(columns=["parcel_local_id", "geometry"], crs="EPSG:4326")
        
        success = writer.write_layer(
            gdf=empty_gdf,
            layer_name="parcel",
            source_id="SRC_EMPTY",
            source_type="parcel_map"
        )
        self.assertFalse(success, "Writing empty GeoDataFrame should return False.")

    def test_02_utility_line_layer_processing(self):
        """Test ingestion and reprojection of utility line corridor vectors (e.g. underground metro/water duct)."""
        line_geom = LineString([(72.8770, 19.0750), (72.8780, 19.0760)])
        utility_gdf = gpd.GeoDataFrame({
            "utility_local_id": ["UTIL_WATER_01"],
            "utility_kind": ["water"],
            "stratum": ["below"],
            "depth_top_m": [2.5],
            "depth_bottom_m": [4.0],
            "corridor_width_m": [1.5],
            "geometry": [line_geom]
        }, crs="EPSG:4326")

        harmonizer = SpatialHarmonizer(target_crs="EPSG:32643")
        harmonized = harmonizer.harmonize_vector(utility_gdf)
        self.assertEqual(harmonized.crs.to_string(), "EPSG:32643")

        writer = GeoPackageWriter(self.gpkg_path)
        success = writer.write_layer(
            gdf=harmonized,
            layer_name="utility_line",
            source_id="SRC_UTILITY_01",
            source_type="utility_map"
        )
        self.assertTrue(success)

        # Verify layer read-back
        gdf_read = gpd.read_file(self.gpkg_path, layer="utility_line")
        self.assertEqual(len(gdf_read), 1)
        self.assertEqual(gdf_read.crs.to_string(), "EPSG:32643")

    def test_03_multipolygon_geometry_support(self):
        """Test that complex MultiPolygon geometries (multi-part parcels) are harmonized cleanly."""
        poly1 = Polygon([(72.8770, 19.0750), (72.8775, 19.0750), (72.8775, 19.0755), (72.8770, 19.0750)])
        poly2 = Polygon([(72.8780, 19.0760), (72.8785, 19.0760), (72.8785, 19.0765), (72.8780, 19.0760)])
        multi_poly = MultiPolygon([poly1, poly2])

        gdf = gpd.GeoDataFrame({
            "parcel_local_id": ["P_MULTI_01"],
            "parent_ulpin_14": ["27402015009999"],
            "geometry": [multi_poly]
        }, crs="EPSG:4326")

        harmonizer = SpatialHarmonizer(target_crs="EPSG:32643")
        harmonized = harmonizer.harmonize_vector(gdf)
        self.assertEqual(harmonized.crs.to_string(), "EPSG:32643")
        self.assertTrue(harmonized.geometry.iloc[0].is_valid)

    def test_04_raster_metadata_inspection(self):
        """Test raster file inspector logic on supported extensions."""
        inspector = FileInspector()
        all_exts = inspector.SUPPORTED_VECTOR_EXTS | inspector.SUPPORTED_RASTER_EXTS
        self.assertIn(".tif", all_exts)
        self.assertIn(".dem", all_exts)

if __name__ == "__main__":
    unittest.main()
