import os
import geopandas as gpd
import rasterio
from typing import Dict, Any, Union

class FileInspector:
    """
    Inspects incoming raw GIS files (vector: GeoJSON, Shapefile, DXF, KML; 
    raster: GeoTIFF, DEM) and extracts metadata for P2 ingestion.
    """

    SUPPORTED_VECTOR_EXTS = {'.geojson', '.shp', '.json', '.kml', '.gpkg', '.dxf'}
    SUPPORTED_RASTER_EXTS = {'.tif', '.tiff', '.dem'}

    def inspect(self, file_path: str) -> Dict[str, Any]:
        """
        Main inspection dispatcher. Determines file type and extracts metadata.
        """
        if not os.path.exists(file_path):
            return {"valid": False, "error": f"File does not exist: {file_path}"}

        ext = os.path.splitext(file_path)[1].lower()

        if ext in self.SUPPORTED_VECTOR_EXTS:
            return self._inspect_vector(file_path)
        elif ext in self.SUPPORTED_RASTER_EXTS:
            return self._inspect_raster(file_path)
        else:
            return {"valid": False, "error": f"Unsupported file extension '{ext}'"}

    def _inspect_vector(self, file_path: str) -> Dict[str, Any]:
        try:
            gdf = gpd.read_file(file_path)
            
            crs_str = gdf.crs.to_string() if gdf.crs else None
            is_valid_crs = crs_str is not None

            # Calculate total bounding box [minx, miny, maxx, maxy]
            bounds = list(gdf.total_bounds) if not gdf.empty else [0, 0, 0, 0]

            geometry_types = list(gdf.geometry.type.unique()) if not gdf.empty else []

            return {
                "valid": True,
                "file_type": "vector",
                "file_name": os.path.basename(file_path),
                "feature_count": len(gdf),
                "crs": crs_str,
                "has_crs": is_valid_crs,
                "geometry_types": geometry_types,
                "bbox": bounds,
                "columns": [col for col in gdf.columns if col != 'geometry'],
                "warning": None if is_valid_crs else "CRS missing in source file!"
            }
        except Exception as e:
            return {"valid": False, "error": f"Failed to parse vector file: {str(e)}"}

    def _inspect_raster(self, file_path: str) -> Dict[str, Any]:
        try:
            with rasterio.open(file_path) as src:
                crs_str = src.crs.to_string() if src.crs else None
                bounds = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]
                
                return {
                    "valid": True,
                    "file_type": "raster",
                    "file_name": os.path.basename(file_path),
                    "width": src.width,
                    "height": src.height,
                    "band_count": src.count,
                    "crs": crs_str,
                    "has_crs": crs_str is not None,
                    "bbox": bounds,
                    "resolution": src.res,
                    "warning": None if crs_str is not None else "CRS missing in raster file!"
                }
        except Exception as e:
            return {"valid": False, "error": f"Failed to parse raster file: {str(e)}"}

if __name__ == "__main__":
    inspector = FileInspector()
    print("File Inspector initialized ready.")
