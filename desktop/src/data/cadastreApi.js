/**
 * Client for the P4 cadastre sidecar.
 *
 * The sidecar is a local FastAPI process, not a server on a network:
 *
 *     ./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000
 *
 * Everything here is read-only except `transition` and `acknowledge`, which are the two
 * actions a reviewer takes. Contract shapes come from `contracts/outbound/*.schema.json`.
 *
 * When the sidecar is not running, callers get nothing and the UI SAYS SO. There is no
 * sample data to fall back to any more — a screen that silently shows invented numbers
 * as though they were the project is worse than one that shows nothing, and the fallback
 * was how it happened.
 */

const BASE = import.meta.env.VITE_CADASTRE_API ?? 'http://127.0.0.1:8000'

/** The project every call reads, set once when the wizard creates one.
 *
 *  Module state rather than a parameter on each call: the alternative threads a path
 *  through every screen, and the first one that forgets reads a *different project* while
 *  claiming to show this one. There is exactly one open project per window, so there is
 *  exactly one of these.
 *
 *  It starts empty on purpose. Before a project exists there is nothing to read, and a
 *  default of `pilot.gpkg` would quietly serve the demo fixture to a fresh install — the
 *  screen would look right and belong to somebody else's data. */
let DB = import.meta.env.VITE_CADASTRE_DB ?? ''

export function setProjectPath(path) {
  DB = path
}

export function projectPath() {
  return DB
}

export class SidecarUnavailable extends Error {}

async function request(path, { method = 'GET', body, params } = {}) {
  const url = new URL(BASE + path)
  for (const [k, v] of Object.entries({ db_path: DB, ...(params ?? {}) })) {
    if (v !== undefined && v !== null) url.searchParams.set(k, v)
  }

  let res
  try {
    res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (cause) {
    // Connection refused, DNS, CORS — the sidecar is not reachable at all.
    throw new SidecarUnavailable(`cadastre sidecar not reachable at ${BASE}`, { cause })
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* a non-JSON error body is still an error; keep the status line */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const cadastre = {
  health: () => request('/cadastre/health'),

  /** The whole project: settings, units, relationships and the latest run's findings. */
  document: () => request('/cadastre/document'),

  unit: (unitId) => request(`/cadastre/units/${encodeURIComponent(unitId)}`),

  /** Import P2's harmonized GeoPackage. Repeatable — identities are not re-minted. */
  ingest: () => request('/cadastre/ingest', { method: 'POST', body: { db_path: DB } }),

  /** Run every validation rule over the project and persist the run. */
  validate: () => request('/cadastre/validate', { method: 'POST', body: { db_path: DB } }),

  latestRun: () => request('/cadastre/runs/latest'),

  /** Errors are not acknowledgeable — the API answers 409. */
  acknowledge: (findingId, actor) =>
    request(`/cadastre/findings/${encodeURIComponent(findingId)}/acknowledge`, {
      method: 'POST',
      body: { actor },
    }),

  /** Approval is guarded: zero errors, every warning acknowledged, a run on record. */
  transition: (unitId, targetStatus, actor, comment) =>
    request(`/cadastre/units/${encodeURIComponent(unitId)}/transition`, {
      method: 'POST',
      body: { target_status: targetStatus, actor, comment },
    }),

  resolveUlpin: (ulpin) => request(`/cadastre/ulpin/${encodeURIComponent(ulpin)}`),

  /** What a project may be built from. Served by the sidecar rather than hardcoded here,
   *  so the wizard's form and `project.py` cannot drift: a type this form offers but the
   *  module does not handle is a file the operator picks and the project silently drops. */
  sourceTypes: () => request('/cadastre/source-types'),

  /** Build a project GeoPackage from the operator's own files, and import it.
   *
   *  Sources are named by path, not uploaded: the sidecar runs on this machine, which is
   *  the whole point of the desktop-first design. A LiDAR tile is read where it lies.
   *
   *  `horizontal_accuracy_m` and `vertical_accuracy_m` are mandatory per source and the
   *  sidecar refuses the call without them — every validation tolerance is derived from
   *  those two numbers, so a default would make each source claim survey grade. */
  createProject: (payload) =>
    request('/cadastre/project', { method: 'POST', body: payload, params: { db_path: null } }),
}

// --- shaping the contract for these screens ------------------------------------------

export const UNIT_TYPE_LABELS = {
  land_parcel: 'Land Parcel',
  building: 'Building',
  floor: 'Floor',
  apartment: 'Apartment',
  underground_feature: 'Underground',
  elevated_structure: 'Elevated',
}

const SEVERITY_TO_UI = { error: 'error', warning: 'warning', info: 'info' }

/** Findings, in the shape the error table renders. */
export function findingsToRows(doc) {
  return (doc.findings ?? []).map((f) => ({
    id: f.finding_id.slice(0, 8),
    findingId: f.finding_id,
    type: SEVERITY_TO_UI[f.severity] ?? 'info',
    category: f.rule_id,
    description: f.message,
    parcel: f.unit_id,
    // The rule's own severity is the severity. A second axis (Critical/High/Medium/Low)
    // was rendered here once; nothing in the contract produces one.
    severity: f.severity === 'error' ? 'Error' : f.severity === 'warning' ? 'Warning' : 'Info',
    acknowledgedBy: f.acknowledged_by,
    measured: f.measured_value,
    tolerance: f.tolerance,
  }))
}

/** Counts for the dashboard tiles, computed from the document rather than hardcoded. */
export function dashboardCounts(doc) {
  const units = doc.units ?? []
  const by = (t) => units.filter((u) => u.unit_type === t).length
  const findings = doc.findings ?? []
  return {
    parcels: by('land_parcel'),
    buildings: by('building'),
    floors: by('floor'),
    apartments: by('apartment'),
    underground: by('underground_feature'),
    elevated: by('elevated_structure'),
    total: units.length,
    needsReview: units.filter((u) => u.status === 'needs_review').length,
    approved: units.filter((u) => u.status === 'approved').length,
    draft: units.filter((u) => u.status === 'draft').length,
    errors: findings.filter((f) => f.severity === 'error').length,
    warnings: findings.filter((f) => f.severity === 'warning').length,
    info: findings.filter((f) => f.severity === 'info').length,
    // FR-03 made visible: units whose height genuinely is not known.
    unknownHeight: units.filter((u) => u.lower_limit === null || u.upper_limit === null).length,
  }
}

/** Rows for the review queue: what is waiting, and what is blocking it. */
export function reviewRows(doc) {
  const findings = doc.findings ?? []
  return (doc.units ?? [])
    .filter((u) => u.status === 'needs_review')
    .map((u) => {
      const mine = findings.filter(
        (f) => f.unit_id === u.unit_id || (f.related_unit_ids ?? []).includes(u.unit_id),
      )
      const errors = mine.filter((f) => f.severity === 'error').length
      const warnings = mine.filter((f) => f.severity === 'warning')
      return {
        id: u.unit_id,
        ulpin: u.ulpin ?? u.ulpin_provisional ?? '— not yet assigned —',
        provisional: !u.ulpin,
        type: UNIT_TYPE_LABELS[u.unit_type] ?? u.unit_type,
        floor: u.attributes?.floor_index ?? null,
        createdBy: u.created_by,
        confidence: u.confidence_score,
        validationState: u.validation_state,
        errors,
        warnings: warnings.length,
        unacknowledged: warnings.filter((f) => !f.acknowledged_by).length,
        // Mirrors lifecycle.transition's guard, so the button state matches the answer.
        approvable: errors === 0 && warnings.every((f) => f.acknowledged_by),
      }
    })
}

/** Rows for ULPIN search. Matches the identifier, the unit id, or the type. */
export function searchRows(doc, query) {
  const q = query.trim().toLowerCase()
  const rows = (doc.units ?? []).map((u) => ({
    ulpin: u.ulpin ?? u.ulpin_provisional ?? u.unit_id,
    provisional: !u.ulpin,
    unitId: u.unit_id,
    type: UNIT_TYPE_LABELS[u.unit_type] ?? u.unit_type,
    floor: u.attributes?.floor_index ?? null,
    status: u.status,
    validationState: u.validation_state,
    lower: u.lower_limit,
    upper: u.upper_limit,
    datum: u.vertical_datum,
  }))
  if (!q) return rows
  return rows.filter(
    (r) =>
      r.ulpin.toLowerCase().includes(q) ||
      r.unitId.toLowerCase().includes(q) ||
      r.type.toLowerCase().includes(q),
  )
}
