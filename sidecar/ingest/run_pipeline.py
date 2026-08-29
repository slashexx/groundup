import os
import sys
import geopandas as gpd
from typing import Optional, Dict, Any

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from pipeline.schema_manager import GeoPackageSchemaManager
from pipeline.file_inspector import FileInspector
from pipeline.harmonizer import SpatialHarmonizer
from pipeline.gpkg_writer import GeoPackageWriter

class GeoDataPipeline:
    """
    Main Pipeline Controller for Person 2 (P2: Geo Data Pipeline).
    Integrates File Inspection, Reprojection, and GeoPackage Storage per contracts/inbound/p2-geopackage.md.
    """

    def __init__(self, gpkg_output_path: str = "output/pilot_area.gpkg", target_crs: str = "EPSG:32643"):
        self.gpkg_path = gpkg_output_path
        self.target_crs = target_crs
        
        self.schema_manager = GeoPackageSchemaManager(self.gpkg_path)
        self.file_inspector = FileInspector()
        self.harmonizer = SpatialHarmonizer(target_crs=self.target_crs)
        self.writer = GeoPackageWriter(self.gpkg_path)

    def setup_project(self) -> str:
        """Ensures GeoPackage parent directory exists."""
        os.makedirs(os.path.dirname(os.path.abspath(self.gpkg_path)), exist_ok=True)
        print(f"[P2 Engine] Initialized project directory for: {self.gpkg_path}")
        return self.gpkg_path

    def process_file(
        self, 
        input_file_path: str, 
        layer_name: str,
        source_id: str,
        source_type: str,
        source_name: str = "Cadastral Survey Import",
        horizontal_accuracy_m: float = 0.05,
        vertical_accuracy_m: float = 0.10,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Full P2 ingestion workflow:
        1. Inspect source file metadata
        2. Read vector data
        3. Reproject & harmonize geometries to projected metric CRS
        4. Save layer (`parcel`, `building_footprint`, `utility_line`) & update `source` table in .gpkg
        """
        print(f"\n[P2 Engine] --- Processing Input File: {input_file_path} ---")

        # 1. Inspect file
        inspection_res = self.file_inspector.inspect(input_file_path)
        if not inspection_res.get("valid"):
            print(f"[P2 Error] Inspection failed: {inspection_res.get('error')}")
            return False

        print(f"[P2 Inspect] File: {inspection_res['file_name']} | CRS: {inspection_res['crs']} | Features: {inspection_res['feature_count']}")

        # 2. Read File into GeoDataFrame
        gdf = gpd.read_file(input_file_path)

        # Apply column mapping if provided (to align with contract column names)
        if column_mapping:
            gdf = gdf.rename(columns=column_mapping)

        # Ensure source_id column exists on vector features
        if "source_id" not in gdf.columns:
            gdf["source_id"] = source_id

        # 3. Harmonize & Reproject to projected metric CRS
        harmonized_gdf = self.harmonizer.harmonize_vector(gdf)

        # 4. Save to GeoPackage
        success = self.writer.write_layer(
            gdf=harmonized_gdf, 
            layer_name=layer_name, 
            source_id=source_id,
            source_type=source_type,
            source_name=source_name,
            horizontal_accuracy_m=horizontal_accuracy_m,
            vertical_accuracy_m=vertical_accuracy_m
        )
        return success

if __name__ == "__main__":
    pipeline = GeoDataPipeline()
    pipeline.setup_project()
    print("[P2 Engine] Ready for file processing per P2 contract.")
