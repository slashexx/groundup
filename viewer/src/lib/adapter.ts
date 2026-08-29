/**
 * P4 outbound contract -> viewer model.
 *
 * Handles the two deliberate deviations the contract makes from typical GeoJSON:
 * 1. footprint_2d coordinates are in the project's projected CRS (metres) —
 *    reprojected here to WGS84 once, at load time.
 * 2. Heights are absolute in the project vertical datum (e.g. EGM2008).
 *    For display we shift them so ground = 0; the raw values are preserved
 *    for the panel. Display ground is derived from the data, never assumed:
 *    parcel.lower_limit - stratum_below_limit_m (the parcel column starts at
 *    the bottom of the legal stratum, not at ground).
 */
import proj4 from 'proj4'
import type { Finding, Severity, ViewerUnit } from './types'

interface RawUnit {
  unit_id: string
  ulpin?: string | null
  ulpin_provisional?: string | null
  unit_type: ViewerUnit['unit_type']
  status: ViewerUnit['status']
  validation_state?: ViewerUnit['validation_state']
  dispute_state?: ViewerUnit['dispute_state']
  created_by: ViewerUnit['created_by']
  confidence_score?: number | null
  source_ids: string[]
  crs: string
  vertical_datum: string
  footprint_2d: { type: 'Polygon'; coordinates: number[][][] }
  lower_limit: number | null
  upper_limit: number | null
  attributes?: Record<string, unknown>
}

interface RawRelationship {
  from_unit_id: string
  to_unit_id: string
  rel_type: string
}

interface RawFinding {
  rule_id: string
  severity: Severity
  unit_id: string
  related_unit_ids?: string[]
  message?: string
  note?: string
  measured_value?: number | null
  tolerance?: number | null
}

export interface FixtureDocument {
  project?: { stratum_below_limit_m?: number }
  units: RawUnit[]
  relationships?: RawRelationship[]
  expected_findings?: RawFinding[]
}

/** UTM EPSG codes (326xx north / 327xx south) cover our pilot areas. */
function projectionFor(crs: string): string {
  const code = Number(crs.replace('EPSG:', ''))
  if (code >= 32601 && code <= 32660) {
    return `+proj=utm +zone=${code - 32600} +datum=WGS84 +units=m +no_defs`
  }
  if (code >= 32701 && code <= 32760) {
    return `+proj=utm +zone=${code - 32700} +south +datum=WGS84 +units=m +no_defs`
  }
  throw new Error(`Unsupported CRS ${crs} — extend projectionFor() in adapter.ts`)
}

function toWgs84Ring(ring: number[][], crs: string): number[][] {
  const proj = projectionFor(crs)
  return ring.map(([x, y]) => proj4(proj, 'EPSG:4326', [x, y]))
}

/**
 * Ground for display. Derived, in order of preference:
 * parcel bottom minus the below-ground stratum limit, then the median of
 * building ground_level_m attributes, then the minimum known lower_limit.
 */
function deriveGroundM(doc: FixtureDocument): number {
  const below = doc.project?.stratum_below_limit_m
  const parcels = doc.units.filter((u) => u.unit_type === 'land_parcel' && u.lower_limit != null)
  if (below != null && parcels.length > 0) {
    return Math.min(...parcels.map((u) => u.lower_limit!)) - below
  }
  const grounds = doc.units
    .map((u) => u.attributes?.ground_level_m)
    .filter((g): g is number => typeof g === 'number')
    .sort((a, b) => a - b)
  if (grounds.length > 0) return grounds[Math.floor(grounds.length / 2)]
  const lowers = doc.units.map((u) => u.lower_limit).filter((l): l is number => l != null)
  return lowers.length > 0 ? Math.min(...lowers) : 0
}

export function fromP4Document(doc: FixtureDocument): ViewerUnit[] {
  const groundM = deriveGroundM(doc)

  const parentOf = new Map<string, string>()
  for (const rel of doc.relationships ?? []) {
    if (rel.rel_type === 'inside') parentOf.set(rel.from_unit_id, rel.to_unit_id)
  }

  const findingsFor = new Map<string, Finding[]>()
  for (const f of doc.expected_findings ?? []) {
    const list = findingsFor.get(f.unit_id) ?? []
    list.push({
      rule_id: f.rule_id,
      severity: f.severity,
      message: f.message ?? f.note ?? f.rule_id,
      related_unit_ids: f.related_unit_ids ?? [],
      measured_value: f.measured_value ?? null,
      tolerance: f.tolerance ?? null,
    })
    findingsFor.set(f.unit_id, list)
  }

  return doc.units.map((u) => ({
    unit_id: u.unit_id,
    label: u.ulpin ?? u.ulpin_provisional ?? u.unit_id,
    ulpin: u.ulpin ?? null,
    unit_type: u.unit_type,
    status: u.status,
    validation_state: u.validation_state ?? 'unvalidated',
    dispute_state: u.dispute_state ?? 'undisputed',
    created_by: u.created_by,
    confidence_score: u.confidence_score ?? null,
    source_ids: u.source_ids,
    parent_id: parentOf.get(u.unit_id) ?? null,
    easement: u.attributes?.easement === true,
    subdivided: typeof u.attributes?.subdivided === 'boolean' ? u.attributes.subdivided : null,
    ring: toWgs84Ring(u.footprint_2d.coordinates[0], u.crs),
    base_m: u.lower_limit == null ? null : u.lower_limit - groundM,
    top_m: u.upper_limit == null ? null : u.upper_limit - groundM,
    raw: {
      lower_limit: u.lower_limit,
      upper_limit: u.upper_limit,
      vertical_datum: u.vertical_datum,
      crs: u.crs,
    },
    findings: findingsFor.get(u.unit_id) ?? [],
  }))
}
