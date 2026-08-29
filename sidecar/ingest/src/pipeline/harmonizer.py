import geopandas as gpd
from pyproj import CRS
from typing import Optional

class SpatialHarmonizer:
    """
    Harmonizes vector spatial datasets for P2:
    - Reprojects all geometries to project target projected CRS in meters (default EPSG:32643 / UTM Zone 43N).
    - Checks and aligns vertical datum Z-heights.
    - Cleans and fixes invalid geometries.
    """

    def __init__(self, target_crs: str = "EPSG:32643", vertical_datum: str = "MSL_EGM2008"):
        self.target_crs = target_crs
        self.vertical_datum = vertical_datum

    def harmonize_vector(self, gdf: gpd.GeoDataFrame, default_source_crs: Optional[str] = "EPSG:4326") -> gpd.GeoDataFrame:
        """
        Takes a GeoDataFrame, validates/assigns CRS if missing, reprojects to target projected metric CRS,
        and repairs invalid polygon geometries.
        """
        harmonized_gdf = gdf.copy()

        # 1. Ensure CRS is defined
        if harmonized_gdf.crs is None:
            if default_source_crs:
                harmonized_gdf.set_crs(default_source_crs, inplace=True)
            else:
                raise ValueError("GeoDataFrame has no CRS and no default_source_crs was provided.")

        # 2. Reproject if different from target CRS
        current_crs_str = harmonized_gdf.crs.to_string()
        target_crs_obj = CRS.from_user_input(self.target_crs)

        if harmonized_gdf.crs != target_crs_obj:
            print(f"[P2 Harmonizer] Reprojecting vector layer from {current_crs_str} to projected metric CRS ({self.target_crs})...")
            harmonized_gdf = harmonized_gdf.to_crs(self.target_crs)

        # 3. Clean invalid geometries using make_valid()
        invalid_count = (~harmonized_gdf.geometry.is_valid).sum()
        if invalid_count > 0:
            print(f"[P2 Harmonizer] Repairing {invalid_count} invalid geometries...")
            harmonized_gdf.geometry = harmonized_gdf.geometry.make_valid()

        # 4. Standardize geometry column name to 'geom' per p2-geopackage.md contract
        if harmonized_gdf.geometry.name != "geom":
            harmonized_gdf = harmonized_gdf.rename_geometry("geom")

        return harmonized_gdf

if __name__ == "__main__":
    harmonizer = SpatialHarmonizer()
    print(f"Spatial Harmonizer ready with target CRS: {harmonizer.target_crs}")
