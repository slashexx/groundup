"""
Pydantic data models for P3 AI Suggestions.
Conforms strictly to contracts/inbound/p3-suggestion.schema.json.
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, field_validator


class SuggestionKind(str, Enum):
    BUILDING_OUTLINE = "building_outline"
    FLOOR_ESTIMATE = "floor_estimate"


class FloorCountMethod(str, Enum):
    NDSM_DIVISION = "ndsm_division"
    FACADE_HISTOGRAM = "facade_histogram"
    MANUAL = "manual"


class ReviewStateEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class ModelProvenance(BaseModel):
    name: str = Field(..., description="Name of the detection model (e.g. yolov8s-seg-buildings)")
    version: str = Field(..., description="Model version string (e.g. 1.0.0)")
    run_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of execution"
    )


class SuggestionAttributes(BaseModel):
    floor_count: Optional[int] = Field(None, ge=1, description="Estimated floor count")
    floor_count_method: Optional[FloorCountMethod] = Field(
        None, description="Method used to calculate floor count"
    )
    ground_level_m: Optional[float] = Field(None, description="Ground elevation in metres")
    roof_level_m: Optional[float] = Field(None, description="Roof top elevation in metres")


class ReviewState(BaseModel):
    state: ReviewStateEnum = Field(ReviewStateEnum.PENDING, description="Human review status")
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    edited_geometry: Optional[Dict[str, Any]] = None


class AISuggestion(BaseModel):
    suggestion_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID identifier for the suggestion"
    )
    kind: SuggestionKind = Field(..., description="Kind of AI suggestion")
    geometry: Dict[str, Any] = Field(
        ..., description="GeoJSON Polygon in PROJECT CRS (metres), not WGS84"
    )
    crs: str = Field(..., pattern=r"^EPSG:[0-9]+$", description="Projected CRS string (e.g. EPSG:32643)")
    source_raster_ids: List[str] = Field(..., min_items=1, description="Source raster IDs used for detection")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0 and 1")
    model: ModelProvenance = Field(..., description="Model provenance metadata")
    attributes: Optional[SuggestionAttributes] = Field(default_factory=SuggestionAttributes)
    review: ReviewState = Field(default_factory=ReviewState)

    def to_contract_dict(self) -> Dict[str, Any]:
        """Convert pydantic model into contract-compliant dictionary format."""
        data = self.model_dump(exclude_none=True)
        # Ensure enum strings are converted
        data["kind"] = self.kind.value
        data["review"]["state"] = self.review.state.value
        if self.attributes and self.attributes.floor_count_method:
            data["attributes"]["floor_count_method"] = self.attributes.floor_count_method.value
        return data
