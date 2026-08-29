import type { UnitType, UnitStatus, UnitFeature, FilterState } from '../types/viewer';

// ── All valid dataset values ─────────────────────────────────────────────────
export const ALL_TYPES: UnitType[] = [
  'parcel',
  'building',
  'floor',
  'apartment',
  'underground',
];

export const ALL_STATUSES: UnitStatus[] = ['draft', 'checked', 'approved', 'error'];

// ── Color palette ─────────────────────────────────────────────────────────────
export const STATUS_COLORS: Record<UnitStatus, string> = {
  draft:    '#eab308',
  checked:  '#3b82f6',
  approved: '#22c55e',
  error:    '#ef4444',
};

export const BG_COLOR         = '#f0f2ef';
export const PARCEL_COLOR     = '#94a3b8';
export const UNDERGROUND_COLOR = '#475569';
export const LINE_COLOR       = '#1c2321';
export const SELECTED_COLOR   = '#0d6b58';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Toggle an item in a list; if list was undefined, uses `all` as the starting set. */
export function toggleItem<T>(all: T[], current: T[] | undefined, item: T): T[] {
  const list = current ?? all;
  if (list.includes(item)) {
    return list.filter((i) => i !== item);
  }
  return [...list, item];
}

/** Filter units against FilterState (types + statuses + query prefix). */
export function filterUnits(units: UnitFeature[], filter: FilterState): UnitFeature[] {
  const types    = filter.types    ?? ALL_TYPES;
  const statuses = filter.statuses ?? ALL_STATUSES;
  const query    = filter.query?.trim().toLowerCase() ?? '';

  return units.filter((unit) => {
    const p = unit.properties;
    if (!types.includes(p.unit_type))    return false;
    if (!statuses.includes(p.status))    return false;
    if (query && !p.ulpin.toLowerCase().startsWith(query)) return false;
    return true;
  });
}

/**
 * Resolve ancestor chain from parent_ulpin, nearest-first (closest ancestor last).
 * Returns an ordered list from root → direct parent.
 */
export function getAncestors(units: UnitFeature[], ulpin: string): UnitFeature[] {
  const ancestors: UnitFeature[] = [];
  let current = units.find((u) => u.properties.ulpin === ulpin || u.id === ulpin);

  while (current && current.properties.parent_ulpin) {
    const parentUlpin = current.properties.parent_ulpin;
    const parent = units.find(
      (u) => u.properties.ulpin === parentUlpin || u.id === parentUlpin
    );
    if (parent) {
      ancestors.unshift(parent);  // prepend so root comes first
      current = parent;
    } else {
      break;
    }
  }

  return ancestors;
}

/** Return all features whose parent_ulpin === ulpin. */
export function getChildren(units: UnitFeature[], ulpin: string): UnitFeature[] {
  return units.filter((u) => u.properties.parent_ulpin === ulpin);
}

/** Get the fill color hex for a given UnitProperties. */
export function getUnitColorHex(
  p: { unit_type: UnitType; status: UnitStatus }
): string {
  if (p.unit_type === 'parcel')      return PARCEL_COLOR;
  if (p.unit_type === 'underground') return UNDERGROUND_COLOR;
  return STATUS_COLORS[p.status] ?? '#999999';
}

/** Determine if a unit should be visible given current filter + slicing + underground state. */
export function isUnitVisible(
  p: { unit_type: UnitType; status: UnitStatus; ulpin: string; base_height: number },
  filter: FilterState,
  sliceHeight: number | null,
  showUnderground: boolean
): boolean {
  const types    = filter.types    ?? ALL_TYPES;
  const statuses = filter.statuses ?? ALL_STATUSES;
  const query    = filter.query?.trim().toLowerCase() ?? '';

  if (!types.includes(p.unit_type))                          return false;
  if (!statuses.includes(p.status))                          return false;
  if (query && !p.ulpin.toLowerCase().startsWith(query))     return false;
  if (!showUnderground && p.unit_type === 'underground')      return false;
  if (
    sliceHeight !== null &&
    p.unit_type !== 'parcel' &&
    p.base_height >= sliceHeight
  ) {
    return false;
  }

  return true;
}
