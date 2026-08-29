"""Footprint + DEM/DSM -> a building unit."""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry

from ..models import ProjectSettings, Unit


def build(footprint: BaseGeometry, dem_path: str, dsm_path: str,
          settings: ProjectSettings, source_ids: list[str]) -> Unit:
    """Create a building unit spanning ground level to roof level."""
    raise NotImplementedError
