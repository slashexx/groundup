import sqlite3
import os
from typing import Dict, Any

class GeoPackageSchemaManager:
    """
    Manages metadata, project settings, and source registry tables for GeoPackage (.gpkg) files
    strictly adhering to contracts/inbound/p2-geopackage.md for P4 consumption.
    """

    def __init__(self, gpkg_path: str):
        self.gpkg_path = gpkg_path

    def ensure_contract_tables(
        self, 
        project_crs: str = "EPSG:32643", 
        vertical_datum: str = "EGM2008",
        stratum_below_limit_m: float = -30.0,
        stratum_above_limit_m: float = 150.0,
        default_plinth_offset_m: float = 0.6,
        default_parapet_deduction_m: float = 0.0,
        ulpin_version: str = "v1",
        ruleset_version: str = "r1"
    ):
        """
        Initializes registry and project settings tables in the GeoPackage file
        per the team contract specification.
        """
        if not os.path.exists(self.gpkg_path):
            return

        conn = sqlite3.connect(self.gpkg_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. project_settings (single-row table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                project_crs TEXT NOT NULL,
                vertical_datum TEXT NOT NULL,
                stratum_below_limit_m REAL NOT NULL,
                stratum_above_limit_m REAL NOT NULL,
                default_plinth_offset_m REAL NOT NULL,
                default_parapet_deduction_m REAL NOT NULL,
                ulpin_version TEXT NOT NULL,
                ruleset_version TEXT NOT NULL
            );
        """)

        cursor.execute("""
            INSERT OR REPLACE INTO project_settings 
            (id, project_crs, vertical_datum, stratum_below_limit_m, stratum_above_limit_m, default_plinth_offset_m, default_parapet_deduction_m, ulpin_version, ruleset_version)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (project_crs, vertical_datum, stratum_below_limit_m, stratum_above_limit_m, default_plinth_offset_m, default_parapet_deduction_m, ulpin_version, ruleset_version))

        # 2. source table (drives P4 validation tolerances)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source (
                source_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                capture_date TEXT NOT NULL,
                crs TEXT NOT NULL,
                vertical_datum TEXT NOT NULL,
                horizontal_accuracy_m REAL NOT NULL,
                vertical_accuracy_m REAL NOT NULL,
                coverage_wkt TEXT NOT NULL,
                processing_status TEXT NOT NULL
            );
        """)

        # 3. raster registry table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raster (
                raster_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                crs TEXT NOT NULL,
                vertical_datum TEXT NOT NULL,
                resolution_m REAL NOT NULL,
                source_id TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES source(source_id)
            );
        """)

        conn.commit()
        conn.close()

    def get_project_settings(self) -> Dict[str, Any]:
        """Returns project settings single row as a dictionary."""
        if not os.path.exists(self.gpkg_path):
            return {}

        conn = sqlite3.connect(self.gpkg_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM project_settings WHERE id = 1;")
            row = cursor.fetchone()
            return dict(row) if row else {}
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()

if __name__ == "__main__":
    manager = GeoPackageSchemaManager("test_output/pilot_area.gpkg")
    print("Schema Manager ready with P2 contract specification.")
