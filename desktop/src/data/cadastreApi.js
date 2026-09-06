/**
 * Client for the P4 cadastre sidecar.
 *
 * The sidecar is a local FastAPI process, not a server on a network:
 *
 *     ./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000
 *
 * Every route that changes the project is named for the decision it records — a reviewer
 * acknowledging a warning, approving a unit, accepting a suggestion — or for the pipeline
 * step it runs. Contract shapes come from `contracts/outbound/*.schema.json`.
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
/** Where the open project is remembered across reloads.
 *
 *  Module state alone is lost on every reload, and the app's only entrance was the
 *  creation wizard - so closing the window meant either finding the project again or
 *  running the wizard over the file, which is how it came to be overwritten. This is a
 *  path, not data: the project lives in the GeoPackage, and this only says which one was
 *  open. A stale path is handled where it is read, by asking the sidecar to open it and
 *  falling back to the wizard when it refuses. */
const REMEMBERED = 'cadastre.project_path'

function remembered() {
  try {
    return window.localStorage.getItem(REMEMBERED) ?? ''
  } catch {
    return ''   // private window, or storage disabled; the wizard is still a way in
  }
}

let DB = import.meta.env.VITE_CADASTRE_DB ?? remembered()

export function setProjectPath(path) {
  DB = path ?? ''
  try {
    if (path) window.localStorage.setItem(REMEMBERED, path)
    else window.localStorage.removeItem(REMEMBERED)
  } catch {
    /* not being able to remember it is not a reason to fail the call that follows */
  }
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
    // The code rides along because a caller sometimes has to tell refusals apart: a 404
    // from `/runs/latest` means validation has never run, which is a different screen
    // from one where the call itself failed.
    const err = new Error(detail)
    err.status = res.status
    throw err
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

  //: Append sources to a project that already exists, and re-ingest. Re-ingesting is
  //  safe to repeat: units match on their source-local id, so the parcels a project
  //  already holds survive with the identifiers issued against them.
  addSources: (sources) =>
    request('/cadastre/sources', { method: 'POST', body: { db_path: DB, sources } }),

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

  /** Give imported buildings a height range, and optionally a floor stack, from the
   *  project's registered rasters. `estimateFloors` divides each envelope by an assumed
   *  storey height — a guess, which the sidecar records as one on every unit it makes. */
  derive: (estimateFloors) =>
    request('/cadastre/derive', {
      method: 'POST',
      body: { db_path: DB, estimate_floors: estimateFloors },
    }),

  /** Run P3 over the project's rasters and queue what it finds. Answers 503 when P3 is
   *  not installed in this environment, which is a different thing from finding nothing
   *  and is shown as such. Nothing here becomes a unit. */
  detect: () => request('/cadastre/detect', { method: 'POST', body: { db_path: DB } }),

  /** The AI review queue. `state` narrows it; omitted, everything comes back. */
  suggestions: (state) => request('/cadastre/suggestions', { params: { state } }),

  /** Accept or reject one suggestion. `edited` is not offered here because it must carry
   *  a corrected outline, and this app has no geometry editor to produce one. */
  reviewSuggestion: (suggestionId, state, actor) =>
    request(`/cadastre/suggestions/${encodeURIComponent(suggestionId)}/review`, {
      method: 'POST',
      body: { state, actor },
    }),

  /** Turn every accepted or edited suggestion into a building unit. Pending and rejected
   *  ones are skipped rather than refused. */
  applySuggestions: () =>
    request('/cadastre/suggestions/apply', { method: 'POST', body: { db_path: DB } }),

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

  /** Open a project that already exists. Read-only: it reports what the file holds and
   *  refuses one that is not a project, rather than initialising a blank one there. */
  /** Move many units at once. Every refusal comes back with the guard's own reason:
   *  a bulk approve reporting only a success count buries the units it could not move,
   *  and which reason applied is exactly what the reviewer's next action depends on. */
  /** Decide many suggestions at once. Not a route around FR-05: the decision still
   *  carries a name, and nothing becomes a unit until `applySuggestions`. Omit `ids` to
   *  act on everything still pending — never on what a person has already ruled on. */
  reviewSuggestions: (state, actor, ids = null) =>
    request('/cadastre/suggestions/review', {
      method: 'POST',
      body: { db_path: DB, state, actor, suggestion_ids: ids },
    }),

  transitionAll: (target, actor, unitIds = null, comment = null) =>
    request('/cadastre/units/transition', {
      method: 'POST',
      body: { db_path: DB, target_status: target, actor, comment, unit_ids: unitIds },
    }),

  openProject: (dbPath) =>
    request('/cadastre/project', { params: { db_path: dbPath } }),
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
        recordedFrom: u.recorded_from ?? null,
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

/** Suggestions, in the shape the AI results list renders.
 *
 * `confidence` arrives as 0..1 and is rendered as a percentage; the conversion happens
 * once, here, because a bar drawn at `width: 0.87%` is indistinguishable from a model
 * that found nothing it believed in.
 */
export function suggestionRows(list) {
  return (list ?? []).map((s) => ({
    id: s.suggestion_id,
    short: s.suggestion_id.slice(0, 8),
    kind: s.kind,
    confidence: s.confidence === null || s.confidence === undefined ? null : s.confidence * 100,
    modelVersion: `${s.model?.name ?? 'unknown'} ${s.model?.version ?? ''}`.trim(),
    runAt: s.model?.run_at ?? null,
    rasters: s.source_raster_ids ?? [],
    // A suggestion that has already produced a unit is settled: the review endpoint
    // answers 409, so the buttons come off rather than offering a decision that is gone.
    unitId: s.unit_id ?? null,
    status: s.review?.state ?? 'pending',
    reviewedBy: s.review?.reviewed_by ?? null,
    attributes: s.attributes ?? {},
  }))
}

// --- export serialisers ---------------------------------------------------------------
//
// Only formats derivable from the outbound document without inventing anything live
// here. CityGML, IFC and KML need a semantic model this block does not hold, and the
// screen says so on the card rather than writing a file that is a rename of another one.

/** Units as a GeoJSON FeatureCollection.
 *
 * The geometry is left in the project CRS, in metres, because that is what
 * `contracts/outbound/unit.schema.json` carries and reprojecting to WGS84 here would put
 * a second, unrecorded transform in the chain. The named CRS member is the pre-RFC-7946
 * form, deliberately: RFC 7946 has no way to state a projected frame, and a reader that
 * assumes degrees would place these polygons in the Gulf of Guinea.
 */
export function unitsToGeoJson(units, crs) {
  return {
    type: 'FeatureCollection',
    crs: { type: 'name', properties: { name: crs } },
    features: units
      .filter((u) => u.footprint_2d)
      .map((u) => ({
        type: 'Feature',
        id: u.unit_id,
        geometry: u.footprint_2d,
        properties: {
          unit_id: u.unit_id,
          ulpin: u.ulpin ?? null,
          ulpin_provisional: u.ulpin_provisional ?? null,
          unit_type: u.unit_type,
          status: u.status,
          validation_state: u.validation_state,
          lower_limit: u.lower_limit,
          upper_limit: u.upper_limit,
          vertical_datum: u.vertical_datum,
          created_by: u.created_by,
          confidence_score: u.confidence_score ?? null,
          floor_index: u.attributes?.floor_index ?? null,
        },
      })),
  }
}

const CSV_COLUMNS = [
  ['unit_id', (u) => u.unit_id],
  ['ulpin', (u) => u.ulpin ?? ''],
  ['ulpin_provisional', (u) => u.ulpin_provisional ?? ''],
  ['unit_type', (u) => u.unit_type],
  ['status', (u) => u.status],
  ['validation_state', (u) => u.validation_state],
  ['lower_limit_m', (u) => u.lower_limit],
  ['upper_limit_m', (u) => u.upper_limit],
  ['crs', (u) => u.crs],
  ['vertical_datum', (u) => u.vertical_datum],
  ['created_by', (u) => u.created_by],
  ['confidence_score', (u) => u.confidence_score],
  ['floor_index', (u) => u.attributes?.floor_index],
  ['recorded_from', (u) => u.recorded_from ?? ''],
]

/** Units as CSV. Geometry is omitted rather than stringified into a cell — a spreadsheet
 *  holding a polygon in one column is not a geospatial export, and offering it as one is
 *  how the wrong file reaches a surveyor. */
export function unitsToCsv(units) {
  const cell = (v) => {
    if (v === null || v === undefined) return ''
    const s = String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [CSV_COLUMNS.map(([name]) => name).join(',')]
  for (const u of units) lines.push(CSV_COLUMNS.map(([, read]) => cell(read(u))).join(','))
  return lines.join('\n')
}
