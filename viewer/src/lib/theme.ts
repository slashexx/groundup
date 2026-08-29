import type { Severity, ValidationState, ViewerUnit } from './types'

/** One palette for both viewers so 2D and 3D always read the same. */
export const VALIDATION_COLORS: Record<ValidationState, string> = {
  unvalidated: '#4a7fb5',
  passed: '#0d6b58',
  passed_with_warnings: '#c9a227',
  failed: '#b3402a',
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  error: '#b3402a',
  warning: '#a15c07',
  info: '#2c5578',
}

export const UNDERGROUND_COLOR = '#5b6663'
export const PARCEL_FILL = '#d8d4c8'
export const PARCEL_OUTLINE = '#8a8578'
/** Units whose vertical extent is unknown — recorded as absent, never guessed. */
export const UNKNOWN_COLOR = '#9aa39e'
export const SELECT_COLOR = '#ffb703'
export const OUTLINE_COLOR = '#1c2321'
export const GROUND_COLOR = '#e8e6df'

/**
 * Base (unselected) color. Type identifies parcels and below-grade features;
 * everything else is colored by its validation state — the check results are
 * what a reviewer needs to see at a glance.
 */
export function unitColor(u: ViewerUnit): string {
  if (u.unit_type === 'land_parcel') return PARCEL_FILL
  if (u.unit_type === 'underground_feature') return UNDERGROUND_COLOR
  if (u.base_m == null || u.top_m == null) return UNKNOWN_COLOR
  return VALIDATION_COLORS[u.validation_state]
}
