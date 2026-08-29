import os
import sqlite3
import datetime
import geopandas as gpd
from typing import Dict, Any, Optional
from .schema_manager import GeoPackageSchemaManager

class GeoPackageWriter:
    """
    Saves harmonized vector layers into the GeoPackage (.gpkg) database 
    and updates the `source` registry table per contracts/inbound/p2-geopackage.md.
    """

    def __init__(self, gpkg_path: str):
        self.gpkg_path = gpkg_path
        self.schema_manager = GeoPackageSchemaManager(gpkg_path)

    def write_layer(
        self, 
        gdf: gpd.GeoDataFrame, 
        layer_name: str, 
        source_id: str,
        source_type: str,
        source_name: str = "Survey Data Ingestion",
        provider: str = "Survey of India / DoLR",
        capture_date: str = "2026-08-29",
        horizontal_accuracy_m: float = 0.05,
        vertical_accuracy_m: float = 0.10,
        vertical_datum: str = "MSL_EGM2008"
    ) -> bool:
        """
        Writes a harmonized GeoDataFrame to a specified layer in the GeoPackage file
        and logs required source accuracy metadata in the `source` table.
        """
        if gdf.empty:
            print(f"[P2 Writer Warning] GeoDataFrame for layer '{layer_name}' is empty. Skipping.")
            return False

        os.makedirs(os.path.dirname(os.path.abspath(self.gpkg_path)), exist_ok=True)

        file_exists = os.path.exists(self.gpkg_path) and os.path.getsize(self.gpkg_path) > 0
        mode = 'a' if file_exists else 'w'

        # 1. Write spatial layer into GeoPackage
        print(f"[P2 Writer] Saving layer '{layer_name}' ({len(gdf)} features) to {self.gpkg_path}...")
        gdf.to_file(self.gpkg_path, layer=layer_name, driver="GPKG", engine="pyogrio", mode=mode)

        # 2. Ensure contract tables exist
        self.schema_manager.ensure_contract_tables(vertical_datum=vertical_datum)

        # 3. Update source registry table (drives P4 validation tolerances)
        conn = sqlite3.connect(self.gpkg_path)
        cursor = conn.cursor()

        crs_str = gdf.crs.to_string() if gdf.crs else "EPSG:32643"
        coverage_geom = gdf.union_all().convex_hull if hasattr(gdf, "union_all") else gdf.unary_union.convex_hull
        coverage_wkt = str(coverage_geom.wkt) if not gdf.empty else "POLYGON EMPTY"

        cursor.execute("""
            INSERT OR REPLACE INTO source 
            (source_id, source_type, name, provider, capture_date, crs, vertical_datum, horizontal_accuracy_m, vertical_accuracy_m, coverage_wkt, processing_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            source_type,
            source_name,
            provider,
            capture_date,
            crs_str,
            vertical_datum,
            float(horizontal_accuracy_m),
            float(vertical_accuracy_m),
            coverage_wkt,
            "processed"
        ))

        conn.commit()
        conn.close()

        print(f"[P2 Writer Success] Layer '{layer_name}' written and registered in 'source' table.")
        return True

if __name__ == "__main__":
    writer = GeoPackageWriter("test_output/pilot_area.gpkg")
    print("GeoPackage Writer ready with P2 contract specification.")
