"""
AI Suggestion Builder & JSON Schema Validator.
Factory for creating P3 AI Suggestions and validating output against contract schema.
"""

import os
import json
from typing import Dict, Any, List, Optional
import jsonschema
from shapely.geometry import Polygon, mapping
from .models import (
    AISuggestion,
    SuggestionKind,
    ModelProvenance,
    SuggestionAttributes,
    ReviewState,
    ReviewStateEnum,
    FloorCountMethod
)


def get_contract_schema_path() -> str:
    """Resolve absolute path to contracts/inbound/p3-suggestion.schema.json."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    schema_path = os.path.join(base_dir, "contracts", "inbound", "p3-suggestion.schema.json")
    return schema_path


class SuggestionBuilder:
    def __init__(self, model_name: str = "yolov8s-seg-buildings", model_version: str = "1.0.0"):
        self.model_provenance = ModelProvenance(name=model_name, version=model_version)
        self.schema_path = get_contract_schema_path()
        self._schema_cache = None

    def _load_schema(self) -> Optional[Dict[str, Any]]:
        """Load JSON schema from disk if available."""
        if self._schema_cache is not None:
            return self._schema_cache

        if os.path.exists(self.schema_path):
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self._schema_cache = json.load(f)
            return self._schema_cache
        return None

    def validate_dict(self, data: Dict[str, Any]) -> bool:
        """Validate a suggestion dictionary against p3-suggestion.schema.json."""
        schema = self._load_schema()
        if schema:
            jsonschema.validate(instance=data, schema=schema)
            return True
        return False

    def create_suggestion(
        self,
        kind: SuggestionKind,
        polygon: Polygon,
        source_raster_ids: List[str],
        crs: str = "EPSG:32643",
        confidence: float = 0.85,
        floor_count: Optional[int] = None,
        floor_count_method: Optional[FloorCountMethod] = None,
        ground_level_m: Optional[float] = None,
        roof_level_m: Optional[float] = None,
        suggestion_id: Optional[str] = None
    ) -> AISuggestion:
        """
        Create a validated AISuggestion instance.
        """
        # Convert shapely polygon to GeoJSON dict
        geom_dict = mapping(polygon)
        # Force type to Polygon
        geom_dict["type"] = "Polygon"

        attributes = SuggestionAttributes(
            floor_count=floor_count,
            floor_count_method=floor_count_method,
            ground_level_m=ground_level_m,
            roof_level_m=roof_level_m
        )

        review = ReviewState(state=ReviewStateEnum.PENDING)

        kwargs = {
            "kind": kind,
            "geometry": geom_dict,
            "crs": crs,
            "source_raster_ids": source_raster_ids,
            "confidence": confidence,
            "model": self.model_provenance,
            "attributes": attributes,
            "review": review
        }
        if suggestion_id:
            kwargs["suggestion_id"] = suggestion_id

        suggestion = AISuggestion(**kwargs)

        # Validate against JSON schema
        suggestion_dict = suggestion.to_contract_dict()
        self.validate_dict(suggestion_dict)

        return suggestion
