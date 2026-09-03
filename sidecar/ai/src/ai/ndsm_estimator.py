"""
nDSM Elevation Statistics & Floor Height Estimator.
Computes nDSM = DSM - DEM, zonal roof/ground stats, and floor counts.
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np
from .models import FloorCountMethod


class NDSMEstimator:
    def __init__(self, default_floor_height_m: float = 3.0):
        self.default_floor_height_m = default_floor_height_m

    def compute_ndsm(self, dsm_array: np.ndarray, dem_array: np.ndarray) -> np.ndarray:
        """Compute normalized Digital Surface Model (nDSM = DSM - DEM)."""
        ndsm = np.subtract(dsm_array, dem_array, dtype=np.float32)
        ndsm[ndsm < 0] = 0.0
        return ndsm

    def estimate_from_arrays(
        self,
        dsm_array: np.ndarray,
        dem_array: np.ndarray,
        mask: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Estimate elevation statistics and floor count from DSM and DEM numpy arrays.
        
        FR-03 Compliance: If height data is missing, invalid, or insufficient,
        floor_count is returned as None with 0.0 confidence.
        """
        if dsm_array is None or dem_array is None or dsm_array.size == 0:
            return {
                "ground_level_m": None,
                "roof_level_m": None,
                "height_m": 0.0,
                "floor_count": None,
                "floor_count_method": None,
                "confidence": 0.0
            }

        # Apply mask if provided
        if mask is not None:
            dsm_vals = dsm_array[mask]
            dem_vals = dem_array[mask]
        else:
            dsm_vals = dsm_array.flatten()
            dem_vals = dem_array.flatten()

        # Clean NaN/Inf values
        valid_idx = np.isfinite(dsm_vals) & np.isfinite(dem_vals)
        dsm_vals = dsm_vals[valid_idx]
        dem_vals = dem_vals[valid_idx]

        if dsm_vals.size == 0 or dem_vals.size == 0:
            return {
                "ground_level_m": None,
                "roof_level_m": None,
                "height_m": 0.0,
                "floor_count": None,
                "floor_count_method": None,
                "confidence": 0.0
            }

        # Zonal statistics
        ground_level = float(np.median(dem_vals))
        # Use 90th percentile for roof level to filter out antenna spikes or noise
        roof_level = float(np.percentile(dsm_vals, 90))
        height_m = max(0.0, roof_level - ground_level)

        # Minimum height for a single story building is ~2.5m
        if height_m < 2.5:
            return {
                "ground_level_m": round(ground_level, 2),
                "roof_level_m": round(roof_level, 2),
                "height_m": round(height_m, 2),
                "floor_count": None,
                "floor_count_method": None,
                "confidence": 0.0
            }

        # Estimate floor count via nDSM division
        raw_floors = height_m / self.default_floor_height_m
        floor_count = int(max(1, round(raw_floors)))

        # Compute confidence based on height variance
        ndsm_vals = dsm_vals - dem_vals
        ndsm_std = float(np.std(ndsm_vals)) if ndsm_vals.size > 1 else 0.0
        relative_noise = ndsm_std / height_m if height_m > 0 else 1.0
        confidence = float(np.clip(1.0 - relative_noise * 0.5, 0.40, 0.90))

        return {
            "ground_level_m": round(ground_level, 2),
            "roof_level_m": round(roof_level, 2),
            "height_m": round(height_m, 2),
            "floor_count": floor_count,
            "floor_count_method": FloorCountMethod.NDSM_DIVISION.value,
            "confidence": round(confidence, 2)
        }
