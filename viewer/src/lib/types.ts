/**
 * P5 viewer model — a display-oriented projection of P4's outbound contract
 * (contracts/outbound/unit.schema.json, finding.schema.json).
 *
 * P4 emits footprints in the project's projected CRS (metres) with heights in
 * the project vertical datum. The adapter (adapter.ts) converts that to what
 * the map engines need — WGS84 rings and heights relative to display ground
 * (ground = 0) — while keeping the raw values for the details panel.
 *
 * Unknown heights stay null all the way to the screen. Never guessed (FR-03).
 */

export type UnitType =
  | 'land_parcel'
  | 'building'
  | 'floor'
  | 'apartment'
  | 'underground_feature'
  | 'elevated_structure'

export type UnitStatus = 'draft' | 'processing' | 'needs_review' | 'approved' | 'replaced' | 'closed'
export type ValidationState = 'unvalidated' | 'passed' | 'passed_with_warnings' | 'failed'
export type Severity = 'error' | 'warning' | 'info'

export interface Finding {
  rule_id: string
  severity: Severity
  message: string
  related_unit_ids: string[]
  measured_value: number | null
  tolerance: number | null
}

export interface ViewerUnit {
  unit_id: string
  /** What humans see: ulpin ?? ulpin_provisional ?? unit_id. */
  label: string
  ulpin: string | null
  unit_type: UnitType
  status: UnitStatus
  validation_state: ValidationState
  dispute_state: 'undisputed' | 'contested'
  created_by: 'human' | 'ai' | 'derived'
  confidence_score: number | null
  source_ids: string[]
  parent_id: string | null
  /** Easements (utilities, tunnels) legitimately cross parcel boundaries. */
  easement: boolean
  /** false = floor has no interior data; apartments deliberately not created. */
  subdivided: boolean | null

  /** Exterior ring in WGS84 [lon, lat] — ready for MapLibre/Cesium. */
  ring: number[][]
  /** Heights relative to display ground (0 = ground). null = unknown. */
  base_m: number | null
  top_m: number | null

  /** Raw contract values, shown verbatim in the details panel. */
  raw: {
    lower_limit: number | null
    upper_limit: number | null
    vertical_datum: string
    crs: string
  }

  findings: Finding[]
}

export interface UnitFilter {
  /** Undefined = no restriction; an empty array matches nothing. */
  types?: UnitType[]
  validation?: ValidationState[]
  /** Case-insensitive substring match on label and unit_id. */
  query?: string
}

/** Shared by Map2D and Viewer3D. No MapLibre/Cesium types may appear here. */
export interface ViewerProps {
  units: ViewerUnit[]
  selectedId: string | null
  filter: UnitFilter
  onSelect: (unitId: string | null) => void
}

export interface Viewer3DProps extends ViewerProps {
  /** Hide everything whose base is at or above this height. null = no cut. */
  sliceHeight: number | null
  /** Fade the ground and reveal below-grade units. */
  showUnderground: boolean
}

export const UNIT_TYPES: UnitType[] = [
  'land_parcel',
  'building',
  'floor',
  'apartment',
  'underground_feature',
  'elevated_structure',
]

export const VALIDATION_STATES: ValidationState[] = [
  'unvalidated',
  'passed',
  'passed_with_warnings',
  'failed',
]

export const TYPE_LABELS: Record<UnitType, string> = {
  land_parcel: 'parcel',
  building: 'building',
  floor: 'floor',
  apartment: 'apartment',
  underground_feature: 'underground',
  elevated_structure: 'elevated',
}

export const VALIDATION_LABELS: Record<ValidationState, string> = {
  unvalidated: 'unvalidated',
  passed: 'passed',
  passed_with_warnings: 'warnings',
  failed: 'failed',
}
