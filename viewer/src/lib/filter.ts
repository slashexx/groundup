import type { UnitFilter, ViewerUnit } from './types'

export function matchesFilter(u: ViewerUnit, f: UnitFilter): boolean {
  if (f.types && !f.types.includes(u.unit_type)) return false
  if (f.validation && !f.validation.includes(u.validation_state)) return false
  if (f.query) {
    const q = f.query.trim().toUpperCase()
    if (!u.label.toUpperCase().includes(q) && !u.unit_id.toUpperCase().includes(q)) return false
  }
  return true
}

export function applyFilter(units: ViewerUnit[], f: UnitFilter): ViewerUnit[] {
  return units.filter((u) => matchesFilter(u, f))
}

export function findUnit(units: ViewerUnit[], unitId: string | null): ViewerUnit | undefined {
  if (!unitId) return undefined
  return units.find((u) => u.unit_id === unitId)
}

/** Chain of ancestors, outermost first (parcel → building → floor …). */
export function ancestorsOf(units: ViewerUnit[], unitId: string): ViewerUnit[] {
  const chain: ViewerUnit[] = []
  let current = findUnit(units, unitId)
  while (current?.parent_id) {
    const parent = findUnit(units, current.parent_id)
    if (!parent) break
    chain.unshift(parent)
    current = parent
  }
  return chain
}

export function childrenOf(units: ViewerUnit[], unitId: string): ViewerUnit[] {
  return units.filter((u) => u.parent_id === unitId)
}

/** [minLon, minLat, maxLon, maxLat] over exterior rings. */
export function bboxOf(units: ViewerUnit[]): [number, number, number, number] | null {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const u of units) {
    for (const [x, y] of u.ring) {
      if (x < minX) minX = x
      if (y < minY) minY = y
      if (x > maxX) maxX = x
      if (y > maxY) maxY = y
    }
  }
  return minX === Infinity ? null : [minX, minY, maxX, maxY]
}

/** Vertical range of known heights, for slice-slider bounds. Parcels excluded. */
export function heightRangeOf(units: ViewerUnit[]): [number, number] {
  let min = 0
  let max = 10
  for (const u of units) {
    if (u.unit_type === 'land_parcel') continue
    if (u.base_m != null && u.base_m < min) min = u.base_m
    if (u.top_m != null && u.top_m > max) max = u.top_m
  }
  return [Math.floor(min - 1), Math.ceil(max + 1)]
}
