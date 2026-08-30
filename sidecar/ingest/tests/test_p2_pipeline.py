import os
import sys
import sqlite3
import unittest
import geopandas as gpd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from run_pipeline import GeoDataPipeline

class TestP2GeoDataPipeline(unittest.TestCase):
    
    def setUp(self):
        self.gpkg_path = "output/contract_test_pilot.gpkg"
        if os.path.exists(self.gpkg_path):
            os.remove(self.gpkg_path)

    def tearDown(self):
        if os.path.exists(self.gpkg_path):
            os.remove(self.gpkg_path)

    def test_pipeline_contract_compliance(self):
        """
        Verifies end-to-end P2 pipeline ingestion, metric reprojection to EPSG:32643,
        and database contract tables (project_settings, source).
        """
        pipeline = GeoDataPipeline(gpkg_output_path=self.gpkg_path, target_crs="EPSG:32643")
        pipeline.setup_project()

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        parcels_file = os.path.join(base_dir, "test_data", "sample_parcels.geojson")
        buildings_file = os.path.join(base_dir, "test_data", "sample_buildings.geojson")

        # 1. Ingest parcel dataset
        res_parcels = pipeline.process_file(
            input_file_path=parcels_file, 
            layer_name="parcel",
            source_id="SRC_PARCEL_MAP_01",
            source_type="parcel_map",
            horizontal_accuracy_m=0.05,
            vertical_accuracy_m=0.10
        )
        self.assertTrue(res_parcels, "Parcel ingestion failed!")

        # 2. Ingest building footprint dataset
        res_buildings = pipeline.process_file(
            input_file_path=buildings_file, 
            layer_name="building_footprint",
            source_id="SRC_FOOTPRINT_DRONE_01",
            source_type="footprint",
            horizontal_accuracy_m=0.08,
            vertical_accuracy_m=0.15
        )
        self.assertTrue(res_buildings, "Building footprint ingestion failed!")

        # 3. Verify SQLite contract tables (`project_settings` & `source`)
        conn = sqlite3.connect(self.gpkg_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check project_settings
        cursor.execute("SELECT * FROM project_settings WHERE id = 1;")
        settings = dict(cursor.fetchone())
        self.assertEqual(settings["project_crs"], "EPSG:32643")

        # Check source table accuracy metadata
        cursor.execute("SELECT source_id, source_type, horizontal_accuracy_m, vertical_accuracy_m FROM source;")
        sources = [dict(r) for r in cursor.fetchall()]
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["horizontal_accuracy_m"], 0.05)

        conn.close()

        # 4. Verify GeoPandas spatial layers in metric projected CRS EPSG:32643
        gdf_parcel = gpd.read_file(self.gpkg_path, layer="parcel")
        self.assertEqual(gdf_parcel.crs.to_string(), "EPSG:32643")
        self.assertIn("parcel_local_id", gdf_parcel.columns)
        self.assertIn("parent_ulpin_14", gdf_parcel.columns)

        gdf_bldg = gpd.read_file(self.gpkg_path, layer="building_footprint")
        self.assertEqual(gdf_bldg.crs.to_string(), "EPSG:32643")
        self.assertIn("building_local_id", gdf_bldg.columns)

if __name__ == "__main__":
    unittest.main()
