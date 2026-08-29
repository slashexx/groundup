"""Domain types, mirroring packages/contracts/outbound/*.schema.json.

The JSON Schemas are the source of truth across languages; these dataclasses are the
Python projection of them. If you change one, change both, and tell the team.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class UnitType(str, Enum):
    LAND_PARCEL = "land_parcel"
    BUILDING = "building"
    FLOOR = "floor"
    APARTMENT = "apartment"
    UNDERGROUND_FEATURE = "underground_feature"
    ELEVATED_STRUCTURE = "elevated_structure"

    @property
    def is_easement(self) -> bool:
        """Easements may legitimately cross parcel boundaries; ownership volumes may not.

        This distinction drives the containment rule. A tunnel confined to a single
        parcel would be the anomaly, not the norm.
        """
        return self in (UnitType.UNDERGROUND_FEATURE, UnitType.ELEVATED_STRUCTURE)


class Status(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REPLACED = "replaced"
    CLOSED = "closed"


class ValidationState(str, Enum):
    UNVALIDATED = "unvalidated"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class DisputeState(str, Enum):
    """Legal contestation. Deliberately separate from ValidationState, which is geometric.

    A cadastre must be able to hold a contradiction without resolving it.
    """
    UNDISPUTED = "undisputed"
    CONTESTED = "contested"


class Representation(str, Enum):
    PRISM = "prism"
    POLYHEDRON = "polyhedron"


class CreatedBy(str, Enum):
    HUMAN = "human"
    AI = "ai"
    DERIVED = "derived"


class Severity(str, Enum):
    ERROR = "error"      # blocks approval
    WARNING = "warning"  # requires reviewer acknowledgement
    INFO = "info"        # advisory


class RuleId(str, Enum):
    GEOM_INVALID = "GEOM_INVALID"
    GEOM_DUPLICATE = "GEOM_DUPLICATE"
    Z_IMPOSSIBLE = "Z_IMPOSSIBLE"
    OVERLAP_SIBLING = "OVERLAP_SIBLING"
    GAP_SIBLING = "GAP_SIBLING"
    ESCAPES_PARENT = "ESCAPES_PARENT"
    FLOOR_SEQUENCE = "FLOOR_SEQUENCE"
    FLOOR_HEIGHT_IMPLAUSIBLE = "FLOOR_HEIGHT_IMPLAUSIBLE"
    UTILITY_CROSSES_BUILDING = "UTILITY_CROSSES_BUILDING"
    CRS_MISMATCH = "CRS_MISMATCH"
    DATUM_MISMATCH = "DATUM_MISMATCH"
    CONFIDENCE_LOW = "CONFIDENCE_LOW"
    PROVENANCE_MISSING = "PROVENANCE_MISSING"


class RelType(str, Enum):
    CONTAINS = "contains"
    INSIDE = "inside"
    OVERLAPS = "overlaps"
    ADJACENT = "adjacent"
    CREATED_FROM = "created_from"
    REPLACED_BY = "replaced_by"


class LedgerState(str, Enum):
    ISSUED = "issued"
    REPLACED = "replaced"
    CLOSED = "closed"


@dataclass(frozen=True)
class Accuracy:
    """Per-source measurement accuracy. Drives every geometric comparison tolerance."""
    horizontal_m: float
    vertical_m: float


@dataclass
class ModelProvenance:
    name: str
    version: str
    run_at: datetime


@dataclass
class Unit:
    """One bounded volume with an identity, a classification, a lifecycle position
    and a paper trail.

    Identity note: `unit_id` is opaque, allocated once, never derived and never reused.
    `ulpin` is a derived locator that is frozen at approval and bound to `unit_id`
    thereafter. They are not the same thing and must not be conflated.
    """

    unit_id: str
    unit_type: UnitType
    status: Status
    crs: str
    vertical_datum: str
    footprint_2d: dict[str, Any]          # GeoJSON Polygon in `crs` (metres), not WGS84
    source_ids: list[str]
    created_by: CreatedBy

    representation: Representation = Representation.PRISM
    validation_state: ValidationState = ValidationState.UNVALIDATED
    dispute_state: DisputeState = DisputeState.UNDISPUTED

    ulpin: str | None = None              # NULL until approved, then frozen forever
    ulpin_provisional: str | None = None  # recomputed freely; discarded at approval
    ulpin_version: str | None = None

    lower_limit: float | None = None      # None means unknown - never guess (FR-03)
    upper_limit: float | None = None

    confidence_score: float | None = None
    model: ModelProvenance | None = None

    valid_from: date | None = None        # when this was true on the ground
    valid_to: date | None = None
    recorded_from: datetime | None = None  # when the system believed it
    recorded_to: datetime | None = None

    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> float | None:
        if self.lower_limit is None or self.upper_limit is None:
            return None
        return self.upper_limit - self.lower_limit


@dataclass
class Finding:
    finding_id: str
    run_id: str
    rule_id: RuleId
    severity: Severity
    unit_id: str
    message: str
    detected_at: datetime

    related_unit_ids: list[str] = field(default_factory=list)
    suggested_action: str | None = None
    affected_geometry: dict[str, Any] | None = None
    measured_value: float | None = None
    tolerance: float | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None


@dataclass
class Relationship:
    from_unit_id: str
    to_unit_id: str
    rel_type: RelType
    created_at: datetime


@dataclass
class LedgerEntry:
    """Proof of FR-06's non-reuse guarantee. Rows are never deleted."""
    ulpin: str
    unit_id: str
    issued_at: datetime
    ulpin_version: str
    state: LedgerState


@dataclass
class ProjectSettings:
    project_crs: str
    vertical_datum: str
    stratum_below_limit_m: float
    stratum_above_limit_m: float
    default_plinth_offset_m: float
    default_parapet_deduction_m: float
    ulpin_version: str
    ruleset_version: str
    min_floor_height_m: float = 2.4
    max_floor_height_m: float = 5.0
    confidence_warn_below: float = 0.6
    tolerance_k: float = 1.0  # 1.0 = 1 sigma; 1.96 for 95% confidence
