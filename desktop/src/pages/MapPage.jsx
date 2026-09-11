import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Polygon, Popup, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Icons } from '../components/Icons';
import { LAYER_GROUP_LABELS, MAP_LAYERS } from '../data/layers';
import { useCadastreDocument } from '../data/useCadastre';
import { UNIT_TYPE_LABELS } from '../data/cadastreApi';
// P5 owns the projected-CRS-to-WGS84 conversion. Importing it rather than copying it
// keeps one implementation: the desktop app and the published web build have to agree
// on where a building is, exactly, and two copies of that maths would drift.
import { fromP4Document } from '../../../viewer/src/lib/adapter';
import proj4 from 'proj4';

/** Units from the live document, split for the two Leaflet layers. */
function useProjectGeometry() {
  const { doc } = useCadastreDocument();
  return useMemo(() => {
    if (!doc) return { parcels: [], buildings: [], bounds: null, sceneUnits: [],
                       projectExtent: null, withHeights: 0, typeCounts: {},
                       unitsById: new Map(), sourcesById: new Map(),
                       findingsByUnit: new Map(), parentOf: new Map(),
                       childrenOf: new Map(), projectProj4: null };

    const units = fromP4Document(doc);
    // Leaflet wants [lat, lng]; the adapter returns GeoJSON order.
    const latlng = (u) => u.ring.map(([lon, lat]) => [lat, lon]);

    const parcels = units.filter((u) => u.unit_type === 'land_parcel');
    const buildings = units.filter((u) => u.unit_type === 'building');

    let bounds = null;
    for (const u of units) {
      for (const [lon, lat] of u.ring) {
        bounds = bounds
          ? [[Math.min(bounds[0][0], lat), Math.min(bounds[0][1], lon)],
             [Math.max(bounds[1][0], lat), Math.max(bounds[1][1], lon)]]
          : [[lat, lon], [lat, lon]];
      }
    }
    // The 3D scene works in the project CRS directly: it is already metres, so a box
    // drawn from these numbers is the real size of the thing. Reprojecting to degrees
    // and back would only lose precision on the way.
    const raw = doc.units ?? [];
    // `contains` gives each floor its building, so selecting one can open its stack.
    const parentOf = new Map();
    for (const r of doc.relationships ?? []) {
      if (r.rel_type === 'contains') parentOf.set(r.to_unit_id, r.from_unit_id);
    }
    const unitsById = new Map(raw.map((u) => [u.unit_id, u]));
    const sourcesById = new Map((doc.sources ?? []).map((s) => [s.source_id, s]));
    const childrenOf = new Map();
    for (const [child, parent] of parentOf) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, []);
      childrenOf.get(parent).push(child);
    }
    // Findings are keyed by unit so a panel can show a unit's own, rather than sending
    // the reader to a project-wide error list to find out whether this one is clean.
    const findingsByUnit = new Map();
    for (const f of doc.findings ?? []) {
      if (!findingsByUnit.has(f.unit_id)) findingsByUnit.set(f.unit_id, []);
      findingsByUnit.get(f.unit_id).push(f);
    }

    const sceneUnits = raw.map((u) => ({
      unit_id: u.unit_id,
      unit_type: u.unit_type,
      label: u.ulpin ?? u.ulpin_provisional ?? u.unit_id,
      lower_limit: u.lower_limit,
      upper_limit: u.upper_limit,
      ringMetres: u.footprint_2d?.coordinates?.[0] ?? [],
      parent_unit_id: parentOf.get(u.unit_id) ?? null,
    })).filter((u) => u.ringMetres.length);

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    let groundZ = Infinity;
    for (const u of sceneUnits) {
      for (const [x, y] of u.ringMetres) {
        if (x < minX) minX = x; if (x > maxX) maxX = x;
        if (y < minY) minY = y; if (y > maxY) maxY = y;
      }
      if (u.unit_type !== 'land_parcel' && u.lower_limit != null && u.lower_limit < groundZ) {
        groundZ = u.lower_limit;
      }
    }
    const projectExtent = Number.isFinite(minX)
      ? { minX, minY, maxX, maxY, groundZ: Number.isFinite(groundZ) ? groundZ : 0 }
      : null;

    // What the project actually holds, per unit type. The layer panel offers a toggle
    // only where there is something to toggle.
    const typeCounts = {};
    for (const u of raw) typeCounts[u.unit_type] = (typeCounts[u.unit_type] ?? 0) + 1;

    return {
      parcels: parcels.map((u) => ({ unit: u, positions: latlng(u) })),
      buildings: buildings.map((u) => ({ unit: u, positions: latlng(u) })),
      bounds,
      typeCounts,
      sceneUnits,
      projectExtent,
      unitsById,
      sourcesById,
      findingsByUnit,
      parentOf,
      childrenOf,
      withHeights: sceneUnits.filter(
        (u) => u.unit_type !== 'land_parcel' && u.lower_limit != null).length,
      projectProj4: doc.project?.project_proj4 ?? null,
    };
  }, [doc]);
}

/** Frame the project once its geometry arrives, and answer the toolbar. */
function FitToProject({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [40, 40] });
  }, [bounds, map]);

  // The toolbar owns no map instance, so it asks by event and this answers.
  useEffect(() => {
    const zoomIn = () => map.zoomIn();
    const zoomOut = () => map.zoomOut();
    const fit = () => bounds && map.fitBounds(bounds, { padding: [40, 40] });
    window.addEventListener('map-zoom-in', zoomIn);
    window.addEventListener('map-zoom-out', zoomOut);
    window.addEventListener('map-fit-project', fit);
    return () => {
      window.removeEventListener('map-zoom-in', zoomIn);
      window.removeEventListener('map-zoom-out', zoomOut);
      window.removeEventListener('map-fit-project', fit);
    };
  }, [map, bounds]);
  return null;
}

/** What the 2D overlay reports, read off the map itself.
 *
 *  The overlay used to state a fixed latitude, longitude, elevation and scale for
 *  Bengaluru, over every project and whatever the map was showing. Leaflet knows where
 *  the pointer is and how far a pixel reaches, so those are reported and nothing else:
 *  there is no elevation here because the project's DEM is a file on disk that only the
 *  sidecar reads, and no "1:2,500" because a scale ratio needs the physical size of the
 *  display, which a browser does not know. Metres per pixel is the same fact without the
 *  invented half.
 */
function MapReadout({ onChange }) {
  const map = useMap();
  const at = useRef(null);
  const lastReport = useRef(0);

  useEffect(() => {
    const report = () => {
      lastReport.current = performance.now();
      const a = map.containerPointToLatLng([0, 0]);
      const b = map.containerPointToLatLng([100, 0]);
      onChange({
        lat: at.current?.lat ?? null,
        lng: at.current?.lng ?? null,
        zoom: map.getZoom(),
        metresPerPixel: map.distance(a, b) / 100,
      });
    };
    // Ten a second. `mousemove` fires per pixel, and each report re-renders a page
    // holding every polygon in the project; a coordinate readout is not worth making
    // the map stutter under the hand that is moving it.
    const move = (e) => {
      at.current = e.latlng;
      if (performance.now() - lastReport.current >= 100) report();
    };
    const out = () => { at.current = null; report(); };

    map.on('mousemove', move);
    map.on('mouseout', out);
    map.on('zoomend', report);
    report();
    return () => {
      map.off('mousemove', move);
      map.off('mouseout', out);
      map.off('zoomend', report);
    };
  }, [map, onChange]);

  return null;
}

/* Fix default Leaflet icon path issue */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

/* Layer Panel component */
/** Why a layer cannot be switched on, or null when it can.
 *
 *  A row that does nothing has to say why it does nothing. The two cases are different
 *  and a reader has to be able to tell them apart: this view does not draw that layer,
 *  or the project holds nothing for it. Neither is a failure, and neither is a checkbox.
 */
function unavailableReason(layer, view, typeCounts) {
  if (!layer.views.includes(view)) {
    return `Not drawn in the ${view.toUpperCase()} view.`;
  }
  if (layer.unitType && !(typeCounts[layer.unitType] > 0)) {
    return `This project holds no ${UNIT_TYPE_LABELS[layer.unitType].toLowerCase()} units.`;
  }
  return null;
}

function LayerPanel({ layers, view, typeCounts, onToggle, onOpacity, onClose }) {
  const [filter, setFilter] = useState('');

  const q = filter.trim().toLowerCase();
  const groups = Object.entries(layers)
    .map(([key, items]) => [key, items.filter((l) => l.label.toLowerCase().includes(q))])
    .filter(([, items]) => items.length);

  return (
    <div className="context-panel">
      <div className="context-panel-header">
        <span className="context-panel-title">LAYERS</span>
        <button className="context-panel-close" onClick={onClose}>
          <Icons.Close style={{ width: 14, height: 14 }} />
        </button>
      </div>
      <div className="context-panel-body">
        {/* The box had no handler at all: typing in it filtered nothing. */}
        <input className="layer-search" placeholder="Filter layers…"
               value={filter} onChange={(e) => setFilter(e.target.value)} />
        {groups.map(([groupKey, items]) => (
          <div className="layer-group" key={groupKey}>
            <div className="layer-group-title">{LAYER_GROUP_LABELS[groupKey]}</div>
            {items.map((layer) => {
              const reason = unavailableReason(layer, view, typeCounts);
              return (
                <div className="layer-item" key={layer.id}
                     style={reason ? { opacity: 0.45 } : undefined} title={reason ?? undefined}>
                  <label style={reason ? { cursor: 'not-allowed' } : undefined}>
                    <input type="checkbox" checked={layer.checked && !reason}
                      disabled={Boolean(reason)}
                      onChange={() => onToggle(groupKey, layer.id)} />
                    <span>{layer.label}</span>
                  </label>
                  <div className="layer-opacity">
                    <input type="range" min="0" max="100" step="5"
                      value={layer.opacity} disabled={Boolean(reason) || !layer.checked}
                      aria-label={`${layer.label} opacity`}
                      onChange={(e) => onOpacity(groupKey, layer.id, Number(e.target.value))} />
                    <span>{layer.opacity}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
        {!groups.length && (
          <div className="layer-group-title" style={{ textTransform: 'none' }}>
            No layer matches “{filter}”.
          </div>
        )}
        <div style={{ marginTop: 'var(--sp-4)', fontSize: 'var(--text-xs)',
                      color: 'var(--text-muted)', lineHeight: 1.6 }}>
          Only layers one of these views actually draws are listed. A project's rasters —
          DEM, DSM, orthophoto — are registered as sources and read when heights are
          derived, but nothing here renders a raster, so there is no switch for one.
        </div>
      </div>
    </div>
  );
}

/* Property Panel component */
/** Shoelace area of a ring already in the project CRS, which is metres. */
function ringArea(ring) {
  let a = 0;
  for (let i = 0, n = ring.length - 1; i < n; i++) {
    a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return Math.abs(a) / 2;
}

const m = (v, digits = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : `${Number(v).toFixed(digits)} m`;

/** Everything the project knows about one unit, assembled for the panel.
 *
 * The panel was written against a mock record and never given a real one: clicking a
 * building set `selectedProperty` to null, so a screen that exists to answer "what is
 * this" answered nothing. Every field below is read off the unit or its registry entry;
 * nothing here is computed to fill a gap, and a value the project does not hold shows as
 * an em dash rather than a plausible number.
 */
function describeUnit(unitId, ctx) {
  const u = ctx.unitsById.get(unitId);
  if (!u) return null;
  const at = u.attributes ?? {};
  const ring = u.footprint_2d?.coordinates?.[0] ?? [];
  const area = ring.length ? ringArea(ring) : null;
  const height = u.lower_limit != null && u.upper_limit != null
    ? u.upper_limit - u.lower_limit : null;

  const parentId = ctx.parentOf.get(unitId);
  const parent = parentId ? ctx.unitsById.get(parentId) : null;
  const children = (ctx.childrenOf.get(unitId) ?? [])
    .map((id) => ctx.unitsById.get(id)).filter(Boolean);

  return {
    unit: u,
    unitId,
    label: u.ulpin ?? u.ulpin_provisional ?? unitId,
    provisional: !u.ulpin && Boolean(u.ulpin_provisional),
    unitType: u.unit_type,
    status: u.status,
    validationState: u.validation_state,
    createdBy: u.created_by,
    confidence: u.confidence_score,
    recordedFrom: u.recorded_from,
    lower: u.lower_limit,
    upper: u.upper_limit,
    height,
    area,
    volume: area != null && height != null ? area * height : null,
    groundLevel: at.ground_level_m,
    roofLevel: at.roof_level_m,
    plinthOffset: at.plinth_offset_m,
    rasterCoverage: at.raster_coverage,
    parcelShare: at.parcel_share,
    parentUlpin14: at.parent_ulpin_14,
    floorIndex: at.floor_index,
    floorHeight: at.floor_height_m,
    floorCount: at.floor_count,
    floorMethod: at.floor_count_method,
    assumedStorey: at.assumed_storey_m,
    localId: at.local_id,
    heightsUnavailable: at.heights_unavailable,
    parent: parent && {
      unitId: parent.unit_id, type: parent.unit_type,
      label: parent.ulpin ?? parent.ulpin_provisional ?? parent.unit_id,
    },
    children: children.map((c) => ({
      unitId: c.unit_id, type: c.unit_type,
      label: c.ulpin ?? c.ulpin_provisional ?? c.unit_id,
      index: c.attributes?.floor_index,
      lower: c.lower_limit, upper: c.upper_limit,
    })).sort((x, y) => (y.lower ?? 0) - (x.lower ?? 0)),
    sources: (u.source_ids ?? []).map(
      (id) => ctx.sourcesById.get(id) ?? { source_id: id }),
    findings: ctx.findingsByUnit.get(unitId) ?? [],
  };
}

function Field({ label, value, hint, tone }) {
  return (
    <div className="property-field">
      <span className="property-field-label" title={hint}>{label}</span>
      <span className="property-field-value" style={tone ? { color: tone } : undefined}>
        {value}
      </span>
    </div>
  );
}

/** How many of a building's floors the lineage list shows before it says so. */
const VISIBLE_CHILDREN = 12;

function PropertyPanel({ property, onClose, onSelectUnit }) {
  if (!property) return null;
  const p = property;
  const isFloor = p.unitType === 'floor' || p.unitType === 'apartment';
  const errors = p.findings.filter((f) => f.severity === 'error');
  const warnings = p.findings.filter((f) => f.severity === 'warning');

  return (
    <div className="property-panel">
      <div className="property-panel-header">
        <span className="property-panel-title">
          {(UNIT_TYPE_LABELS[p.unitType] ?? p.unitType).toUpperCase()}
        </span>
        <button className="context-panel-close" onClick={onClose}>
          <Icons.Close style={{ width: 14, height: 14 }} />
        </button>
      </div>
      <div className="property-panel-body">
        <div className="property-ulpin">
          <span className="property-ulpin-code">{p.label}</span>
          <span className={`status-badge ${p.status}`}>{p.status.replace(/_/g, ' ')}</span>
        </div>
        {p.provisional && (
          <div className="property-note">
            Provisional. The identifier is frozen to this unit only at approval, so it can
            still change until then.
          </div>
        )}

        <div className="property-section">
          <div className="property-section-title">Extent</div>
          <Field label={isFloor ? 'Floor' : 'Storeys'}
                 value={isFloor
                   ? (p.floorIndex === undefined ? '—' : `index ${p.floorIndex}`)
                   : (p.floorCount ?? '—')} />
          <Field label="Base" value={m(p.lower, 2)}
                 hint="Absolute level in the project's vertical datum" />
          <Field label="Top" value={m(p.upper, 2)} />
          <Field label="Height" value={m(p.height, 2)} />
          <Field label="Footprint" value={p.area == null ? '—' : `${p.area.toFixed(1)} m²`} />
          <Field label="Volume"
                 value={p.volume == null ? '—' : `${p.volume.toFixed(0)} m³`}
                 hint="Footprint area times height: this unit is a prism, so this is exact" />
        </div>

        {p.heightsUnavailable && (
          <div className="property-note property-note-warn">{p.heightsUnavailable}</div>
        )}

        {!isFloor && (p.groundLevel != null || p.roofLevel != null) && (
          <div className="property-section">
            <div className="property-section-title">How this height was measured</div>
            <Field label="Ground (DEM)" value={m(p.groundLevel, 2)} />
            <Field label="Roof (DSM)" value={m(p.roofLevel, 2)} />
            <Field label="Plinth offset" value={m(p.plinthOffset, 2)}
                   hint="Indian construction sits above surrounding ground; a project setting, not a constant" />
            <Field label="Raster coverage"
                   value={p.rasterCoverage == null ? '—' : `${(p.rasterCoverage * 100).toFixed(1)}%`}
                   tone={p.rasterCoverage != null && p.rasterCoverage < 0.6
                     ? 'var(--status-warning)' : undefined}
                   hint="Fraction of the footprint with valid elevation. Thin coverage is refused, not averaged." />
          </div>
        )}

        {p.floorMethod && (
          <div className="property-section">
            <div className="property-section-title">Storey count is an estimate</div>
            <div className="property-note property-note-warn">
              Divided by an assumed {m(p.assumedStorey, 1)} storey height
              ({p.floorMethod}). Nothing measured how this building is actually divided,
              which is why the confidence below is low.
            </div>
          </div>
        )}

        <div className="property-section">
          <div className="property-section-title">Record</div>
          <Field label="Validation"
                 value={p.validationState.replace(/_/g, ' ')}
                 tone={p.validationState === 'failed' ? 'var(--status-error)'
                   : p.validationState === 'passed' ? 'var(--status-success)'
                   : 'var(--status-warning)'} />
          <Field label="Errors" value={errors.length}
                 tone={errors.length ? 'var(--status-error)' : 'var(--status-success)'} />
          <Field label="Warnings" value={warnings.length}
                 tone={warnings.length ? 'var(--status-warning)' : 'var(--status-success)'} />
          <Field label="Created by" value={p.createdBy} />
          <Field label="Confidence"
                 value={p.confidence == null ? 'n/a — not AI-derived' : p.confidence.toFixed(2)}
                 tone={p.confidence != null && p.confidence < 0.6
                   ? 'var(--status-warning)' : undefined} />
          {p.localId && <Field label="Source id" value={p.localId} />}
          <Field label="Recorded"
                 value={p.recordedFrom ? new Date(p.recordedFrom).toLocaleString() : '—'} />
        </div>

        {p.findings.length > 0 && (
          <div className="property-section">
            <div className="property-section-title">Findings</div>
            {p.findings.map((f) => (
              <div key={f.finding_id} className={`property-finding ${f.severity}`}>
                <div className="property-finding-rule">{f.rule_id}</div>
                <div className="property-finding-message">{f.message}</div>
              </div>
            ))}
          </div>
        )}

        <div className="property-section">
          <div className="property-section-title">Where this came from</div>
          {p.sources.length === 0 && <div className="property-note">No source recorded.</div>}
          {p.sources.map((s) => (
            <div className="property-source" key={s.source_id}>
              <div className="property-source-name">{s.name ?? s.source_id}</div>
              <div className="property-source-meta">
                {[s.source_type, s.provider, s.capture_date].filter(Boolean).join(' · ') || s.source_id}
              </div>
              <div className="property-source-meta">
                {s.horizontal_accuracy_m == null
                  ? 'accuracy not recorded — tolerances fall back to a default'
                  : `± ${s.horizontal_accuracy_m} m horizontal, ± ${s.vertical_accuracy_m} m vertical`}
              </div>
            </div>
          ))}
        </div>

        <div className="property-section">
          <div className="property-section-title">Lineage</div>
          {p.parent ? (
            <button className="property-link" onClick={() => onSelectUnit(p.parent.unitId)}>
              <span className="property-field-label">
                {UNIT_TYPE_LABELS[p.parent.type] ?? p.parent.type}
              </span>
              <span className="property-field-value">{p.parent.label}</span>
            </button>
          ) : (
            <Field label="Parent" value={p.parentUlpin14 ?? '—'}
                   hint="The 14-character parcel identifier this unit was minted under" />
          )}
          {p.children.length > 0 && (
            <>
              <div className="property-field">
                <span className="property-field-label">Contains</span>
                <span className="property-field-value">{p.children.length}</span>
              </div>
              {p.children.slice(0, VISIBLE_CHILDREN).map((c) => (
                <button className="property-link" key={c.unitId}
                        onClick={() => onSelectUnit(c.unitId)}>
                  <span className="property-field-label">
                    {c.index === undefined ? UNIT_TYPE_LABELS[c.type] ?? c.type
                      : c.index === 0 ? 'Ground' : `Level ${c.index}`}
                  </span>
                  <span className="property-field-value">{m(c.lower, 1)} – {m(c.upper, 1)}</span>
                </button>
              ))}
              {p.children.length > VISIBLE_CHILDREN && (
                <div className="property-note">
                  Showing the {VISIBLE_CHILDREN} highest of {p.children.length}. The rest
                  are in the record, not missing — a forty-storey tower listing twelve
                  levels reads as a twelve-storey building.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* 3D Scene with Three.js */
/** Which layer switch governs each unit type in the scene.
 *
 *  Floors and apartments are absent on purpose: what draws them is which building is
 *  open, not a layer, and the panel offers no switch that would claim otherwise.
 */
const SCENE_LAYER_OF_TYPE = {
  land_parcel: 'parcels',
  building: 'envelopes',
  underground_feature: 'underground',
  elevated_structure: 'elevated',
};

function ThreeScene({ selectedBuilding, onSelectBuilding, activeFloor, sceneLayers }) {
  // Read the project here rather than take it as a prop: this is a sibling of the 2D
  // map, not a child of it, and the hook is memoised on the document so both views work
  // from one parse of it.
  const { sceneUnits, projectExtent, withHeights, projectProj4 } = useProjectGeometry();

  const canvasRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const animFrameRef = useRef(null);
  const selectRef = useRef(onSelectBuilding);
  selectRef.current = onSelectBuilding;

  // Nothing to draw is a state this effect has to handle, not a reason to skip the hook.
  // The empty-state return used to sit above these declarations, so the first project to
  // gain heights changed the hook count between renders and React tore the view down.
  const drawable = Boolean(projectExtent) && withHeights > 0;

  useEffect(() => {
    let mounted = true;
    let controls = null;
    let observer = null;
    let onClick = null;

    async function initScene() {
      if (!drawable) return;
      const THREE = await import('three');
      const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
      if (!mounted || !canvasRef.current) return;

      const host = canvasRef.current;
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x0a0e1a);
      sceneRef.current = scene;

      const cx = (projectExtent.minX + projectExtent.maxX) / 2;
      const cz = (projectExtent.minY + projectExtent.maxY) / 2;
      const groundZ = projectExtent.groundZ;
      const spanX = projectExtent.maxX - projectExtent.minX;
      const spanY = projectExtent.maxY - projectExtent.minY;
      const span = Math.max(spanX, spanY, 20);

      // No fog. Density here is a per-scene constant that silently encodes an assumed
      // scene size, and this scene's size is whatever the project happens to be. The
      // original 0.015 was tuned for a hand-built block tens of metres across; over a
      // 689 m ward it left every building at exp(-(689*0.015)^2) of its colour, which is
      // zero to about forty decimal places. Scaling it by the span was still wrong - the
      // camera has to stand further out than the span to frame it, so the far side of a
      // correctly-scaled scene still sat behind 98% fog. The view was never failing to
      // draw the buildings; it was drawing them and painting the background over them.
      // A depth cue is not worth a class of bug that looks exactly like a dead renderer.

      const w = host.clientWidth || 800;
      const h = host.clientHeight || 600;
      const camera = new THREE.PerspectiveCamera(50, w / h, 0.5, span * 12);
      cameraRef.current = camera;

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(w, h);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      host.appendChild(renderer.domElement);
      rendererRef.current = renderer;

      const ambient = new THREE.AmbientLight(0x8899bb, 1.1);
      scene.add(ambient);
      const dirLight = new THREE.DirectionalLight(0xffffff, 1.4);
      dirLight.position.set(span * 0.5, span * 0.8, span * 0.4);
      scene.add(dirLight);
      const fill = new THREE.DirectionalLight(0x00d4aa, 0.35);
      fill.position.set(-span * 0.4, span * 0.3, -span * 0.5);
      scene.add(fill);

      const groundSpan = span * 1.6;
      const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(groundSpan, groundSpan),
        new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.95 }));
      ground.rotation.x = -Math.PI / 2;
      scene.add(ground);
      const grid = new THREE.GridHelper(groundSpan, 48, 0x1e293b, 0x161d2d);
      grid.position.y = 0.02;
      scene.add(grid);

      // The basemap, draped onto the ground. The 2D view shows the same tiles through
      // Leaflet; here they are stitched onto a canvas, dark-filtered exactly as the 2D
      // pane is, and laid under the scene with every plane vertex reprojected through
      // the project CRS, so a building stands on the same spot of the same road in both
      // views. Loaded after the scene starts animating: an unreachable tile server
      // costs the drape, never the buildings.
      if (sceneLayers.basemap?.on && projectProj4) {
        (async () => {
          try {
            const toLL = (x, y) => proj4(projectProj4, 'EPSG:4326', [x, y]);
            const toM = (lon, lat) => proj4('EPSG:4326', projectProj4, [lon, lat]);
            const half = groundSpan / 2;
            const [wLon, sLat] = toLL(cx - half, cz - half);
            const [eLon, nLat] = toLL(cx + half, cz + half);
            const zTile = 16;
            const n = 2 ** zTile;
            const lon2t = (lon) => ((lon + 180) / 360) * n;
            const lat2t = (lat) => ((1 - Math.log(Math.tan(lat * Math.PI / 180)
              + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2) * n;
            const t2lon = (tx) => (tx / n) * 360 - 180;
            const t2lat = (ty) => {
              const g = Math.PI - (2 * Math.PI * ty) / n;
              return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(g) - Math.exp(-g)));
            };
            const tx0 = Math.floor(lon2t(wLon)), tx1 = Math.floor(lon2t(eLon));
            const ty0 = Math.floor(lat2t(nLat)), ty1 = Math.floor(lat2t(sLat));
            const cols = tx1 - tx0 + 1, rows = ty1 - ty0 + 1;
            if (cols * rows > 120) return;            // a span that big has no business draped
            const cvs = document.createElement('canvas');
            cvs.width = cols * 256; cvs.height = rows * 256;
            const ctx = cvs.getContext('2d');
            // the same treatment .basemap-dark applies to the 2D tile pane
            ctx.filter = 'invert(1) hue-rotate(180deg) brightness(0.85) contrast(0.9) saturate(0.6)';
            await Promise.all(Array.from({ length: cols * rows }, (_, i) => {
              const dx = i % cols, dy = Math.floor(i / cols);
              return new Promise((resolve) => {
                const img = new Image();
                img.crossOrigin = 'anonymous';
                img.onload = () => { ctx.drawImage(img, dx * 256, dy * 256); resolve(); };
                img.onerror = resolve;                // a missing tile is a dark square, not a failure
                img.src = `https://tile.openstreetmap.org/${zTile}/${tx0 + dx}/${ty0 + dy}.png`;
              });
            }));
            if (!mounted) return;
            const texture = new THREE.CanvasTexture(cvs);
            texture.colorSpace = THREE.SRGBColorSpace;
            texture.anisotropy = 4;
            // The drape replaces the ground rather than floating just above it. At a
            // couple of kilometres the depth buffer resolves about half a metre, so two
            // planes 4 cm apart win pixels at random every frame - a blue shimmer over
            // the whole map. One plane cannot fight itself.
            scene.remove(ground);
            scene.remove(grid);
            // Each vertex is reprojected individually: mercator north and grid north
            // disagree by the meridian convergence, and one flat quad would smear that
            // disagreement across the whole campus.
            const SEG = 24;
            const geo = new THREE.PlaneGeometry(1, 1, SEG, SEG);
            const pos = geo.attributes.position;
            for (let i = 0; i < pos.count; i++) {
              const u = pos.getX(i) + 0.5;            // 0..1 across the canvas
              const v = 0.5 - pos.getY(i);            // 0..1 down the canvas
              const [mx, my] = toM(t2lon(tx0 + u * cols), t2lat(ty0 + v * rows));
              pos.setXYZ(i, mx - cx, 0, -(my - cz));
            }
            geo.computeVertexNormals();
            const drape = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
              map: texture,
              transparent: sceneLayers.basemap.alpha < 1,
              opacity: sceneLayers.basemap.alpha,
            }));
            scene.add(drape);
          } catch {
            /* no drape; the plain ground plane stands */
          }
        })();
      }

      // Footprints as outlines on the ground, the 2D layer's counterpart: the trace of
      // each building where it meets the earth, visible even under its envelope.
      if (sceneLayers.footprints?.on) {
        for (const u of sceneUnits.filter((x) => x.unit_type === 'building')) {
          // A metre of clearance, not centimetres: the depth buffer cannot separate
          // 8 cm from the drape at this scene's distances, and a line that loses that
          // fight flickers. A metre is invisible from any orbit height and always wins.
          const pts = u.ringMetres.map(([x, y]) => new THREE.Vector3(x - cx, 1.0, -(y - cz)));
          scene.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            new THREE.LineBasicMaterial({ color: 0x0ea5e9,
                                          opacity: 0.85 * (sceneLayers.footprints.alpha ?? 1),
                                          transparent: true })));
        }
      }

      const TYPE_COLOR = {
        land_parcel: 0x00d4aa,
        building: 0x0ea5e9,
        floor: 0x8b5cf6,
        apartment: 0xf59e0b,
        underground_feature: 0xf59e0b,
        elevated_structure: 0x38bdf8,
      };

      // The layer panel's switches, applied where the geometry is built. A checkbox is
      // only a report of state if the thing it names is genuinely absent when it is off.
      const shown = (type) => {
        const key = SCENE_LAYER_OF_TYPE[type];
        return key ? sceneLayers[key].on : true;
      };
      const alpha = (type) => {
        const key = SCENE_LAYER_OF_TYPE[type];
        return key ? sceneLayers[key].alpha : 1;
      };

      // Parcels as outlines on the ground, so a building always sits inside something.
      if (shown('land_parcel')) {
        for (const u of sceneUnits.filter((x) => x.unit_type === 'land_parcel')) {
          const pts = u.ringMetres.map(([x, y]) => new THREE.Vector3(x - cx, 1.2, -(y - cz)));
          scene.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            new THREE.LineBasicMaterial({ color: TYPE_COLOR.land_parcel,
                                          opacity: 0.5 * alpha('land_parcel'),
                                          transparent: true })));
        }
      }

      // Every unit with a vertical extent becomes the prism it actually is: its own
      // footprint, extruded between its own limits. A unit whose heights are unknown is
      // not drawn at all rather than given an invented one.
      //
      // Buildings always; floors only for the one selected. A ward of 910 buildings is
      // 5,000 floors, and drawing them all is ~12,000 meshes - the scene stops being
      // navigable, and a solid block of overlapping translucent boxes shows less than
      // the envelopes do. Click a building to open its stack.
      const withHeight = (u) => u.lower_limit != null && u.upper_limit != null;
      const solid = sceneUnits.filter((u) => {
        if (u.unit_type === 'land_parcel' || !withHeight(u)) return false;
        if (u.unit_type === 'floor' || u.unit_type === 'apartment') {
          return u.parent_unit_id === selectedBuilding;
        }
        return shown(u.unit_type);
      });

      const pickable = [];
      for (const u of solid) {
        const shape = new THREE.Shape();
        u.ringMetres.forEach(([x, y], i) => {
          const px = x - cx, pz = -(y - cz);
          if (i === 0) shape.moveTo(px, pz); else shape.lineTo(px, pz);
        });
        const height = Math.max(u.upper_limit - u.lower_limit, 0.05);
        const geom = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false });
        geom.rotateX(-Math.PI / 2);

        const selected = selectedBuilding === u.unit_id || activeFloor === u.unit_id;
        const isFloor = u.unit_type === 'floor' || u.unit_type === 'apartment';
        const color = selected ? 0x00ff88 : (TYPE_COLOR[u.unit_type] ?? 0x64748b);
        // Buildings are opaque by default. Nine hundred translucent boxes stacked
        // front-to-back average out to one flat wash of colour, and depth is the whole
        // point here — but the layer's own opacity is the operator's call, not ours.
        const opacity = isFloor ? 0.35 : alpha(u.unit_type);
        const mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({
          color, roughness: 0.55, metalness: 0.05,
          transparent: isFloor || opacity < 1, opacity,
          emissive: color, emissiveIntensity: selected ? 0.45 : 0.06,
        }));
        mesh.position.y = u.lower_limit - groundZ;
        mesh.userData = { unitId: u.unit_id, label: u.label, type: u.unit_type,
                          buildingId: u.unit_type === 'building' ? u.unit_id : u.parent_unit_id };
        scene.add(mesh);
        // Floors of the open building are pickable too: the stack is drawn, so a
        // click on one has to reach it rather than fall through to the envelope.
        pickable.push(mesh);

        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geom),
          new THREE.LineBasicMaterial({ color: selected ? 0x00ff88 : 0x1b3a52,
                                        opacity: 0.5 * opacity, transparent: true }));
        edges.position.y = mesh.position.y;
        scene.add(edges);
      }

      // Frame the project by fitting its bounding sphere to the field of view, rather
      // than guessing a multiple of its width. At 689 m across, the old radius put the
      // camera 620 m out and pointed it at a spot five metres above the origin.
      const radius = Math.hypot(spanX, spanY) / 2;
      const dist = (radius / Math.sin((camera.fov * Math.PI / 180) / 2)) * 0.62;
      camera.position.set(dist * 0.7, dist * 0.6, dist * 0.7);

      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.target.set(0, 0, 0);
      controls.maxPolarAngle = Math.PI / 2.05;   // never go below the ground plane
      controls.minDistance = 15;
      controls.maxDistance = span * 4;
      controls.update();

      // The HUD has said "Mode: Orbit" since the first mock. Nothing orbited on demand:
      // the camera flew a fixed circle and ignored the mouse entirely, so a click on a
      // building did nothing and its floor stack could never be opened.
      const raycaster = new THREE.Raycaster();
      const pointer = new THREE.Vector2();
      let downAt = null;
      const onDown = (e) => { downAt = [e.clientX, e.clientY]; };
      onClick = (e) => {
        // An orbit drag ends in a click event too; only treat a stationary press as a pick.
        if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4) return;
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObjects(pickable, false)[0];
        if (hit) selectRef.current?.(hit.object.userData.unitId);
      };
      renderer.domElement.addEventListener('pointerdown', onDown);
      renderer.domElement.addEventListener('click', onClick);

      function animate() {
        animFrameRef.current = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      }
      animate();

      // The window never resizes when the Layers panel slides in, but the canvas does.
      // Watching the element rather than the window keeps the aspect honest either way.
      observer = new ResizeObserver(() => {
        const cw = host.clientWidth, ch = host.clientHeight;
        if (!cw || !ch) return;
        camera.aspect = cw / ch;
        camera.updateProjectionMatrix();
        renderer.setSize(cw, ch);
      });
      observer.observe(host);
    }

    initScene();

    return () => {
      mounted = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      observer?.disconnect();
      controls?.dispose();
      const r = rendererRef.current;
      if (r) {
        if (onClick) r.domElement.removeEventListener('click', onClick);
        r.dispose();
        if (canvasRef.current && r.domElement.parentNode === canvasRef.current) {
          canvasRef.current.removeChild(r.domElement);
        }
        rendererRef.current = null;
      }
    };
  }, [selectedBuilding, activeFloor, sceneUnits, projectExtent, drawable, sceneLayers]);

  // A 3D view of units that have no third dimension is an empty grid, and an empty grid
  // is indistinguishable from a broken renderer. Say which it is. The heights are
  // genuinely absent - FR-03 forbids inventing them - so this is the honest state, not
  // an error, and it names the step that fills them in.
  if (projectExtent && withHeights === 0) {
    return (
      <div className="scene-empty">
        <div className="scene-empty-title">No heights to draw yet</div>
        <div className="scene-empty-body">
          This project has {sceneUnits.filter((u) => u.unit_type === 'building').length} buildings
          and no elevation, so nothing has a vertical extent. That is the system refusing
          to invent one, not a failure to render.
          <br /><br />
          Add a DEM and a DSM on the Upload Data screen, then run Floor segmentation under
          AI Tools: the buildings get a height range and a floor stack, and this view fills in.
        </div>
      </div>
    );
  }

  return <div ref={canvasRef} className="three-canvas-wrapper" />;
}

/* Floor slider for 3D view */
/** Driven by the floors that exist, not by a `floors` count on a mock building record.
 *  A derived building carries no such field, so the old slider rendered zero buttons for
 *  every real project - a control that is present, empty and silent. */
function FloorSlider({ floors, activeFloor, onFloorChange }) {
  if (!floors.length) return null;
  const ordered = [...floors].sort((a, b) => (b.lower_limit ?? 0) - (a.lower_limit ?? 0));
  return (
    <div className="floor-slider">
      {ordered.map((f, i) => (
        <button
          key={f.unit_id}
          className={`floor-btn${activeFloor === f.unit_id ? ' active' : ''}`}
          title={f.label}
          onClick={() => onFloorChange(activeFloor === f.unit_id ? null : f.unit_id)}
        >
          {i === 0 ? 'Roof' : `${ordered.length - 1 - i}F`}
        </button>
      ))}
    </div>
  );
}

export default function MapPage({ project, view = '2d' }) {
  const navigate = useNavigate();
  const [showLayers, setShowLayers] = useState(true);
  const [layers, setLayers] = useState(MAP_LAYERS);
  const [selectedProperty, setSelectedProperty] = useState(null);
  // 'B318' was a mock identifier from the sample scene. It matched no real unit, so the
  // HUD reported a selection that did not exist and the floor stack had nothing to open.
  const [selectedBuildingId, setSelectedBuildingId] = useState(null);
  const [activeFloor, setActiveFloor] = useState(null);
  const [readout, setReadout] = useState(null);

  useEffect(() => {
    const handleToggleLayers = () => setShowLayers(prev => !prev);
    window.addEventListener('toggle-layers', handleToggleLayers);
    return () => window.removeEventListener('toggle-layers', handleToggleLayers);
  }, []);

  const setLayer = (group, id, change) => {
    setLayers(prev => ({
      ...prev,
      [group]: prev[group].map(l => l.id === id ? { ...l, ...change(l) } : l)
    }));
  };
  const toggleLayer = (group, id) => setLayer(group, id, l => ({ checked: !l.checked }));
  const setOpacity = (group, id, opacity) => setLayer(group, id, () => ({ opacity }));

  const geometry = useProjectGeometry();
  const { parcels: livePercels, buildings: liveBuildings, bounds, typeCounts,
          sceneUnits, projectExtent, withHeights } = geometry;

  // One flat view of the switches, so a renderer asks "is this on" rather than hunting
  // the group a layer happens to live in.
  const layerById = useMemo(
    () => Object.fromEntries(Object.values(layers).flat().map(l => [l.id, l])), [layers]);
  const drawn = (id) => {
    const l = layerById[id];
    if (!l || !l.checked) return false;
    // A toggle for a layer the project has nothing for is disabled in the panel; this is
    // the same rule at the point of drawing, so the two cannot drift apart.
    return !l.unitType || typeCounts[l.unitType] > 0;
  };
  const alpha = (id) => (layerById[id]?.opacity ?? 100) / 100;

  // Memoised because the 3D scene is rebuilt whenever this changes: a new object every
  // render would tear down and re-extrude every mesh on every keystroke elsewhere.
  const sceneLayers = useMemo(() => ({
    parcels: { on: drawn('parcels'), alpha: alpha('parcels') },
    envelopes: { on: drawn('envelopes'), alpha: alpha('envelopes') },
    underground: { on: drawn('underground'), alpha: alpha('underground') },
    elevated: { on: drawn('elevated'), alpha: alpha('elevated') },
    basemap: { on: drawn('basemap'), alpha: alpha('basemap') },
    footprints: { on: drawn('footprints'), alpha: alpha('footprints') },
  }), [layerById, typeCounts]);   // `drawn` and `alpha` read only these two

  // Held stable so that a re-render — the cursor readout updates ten times a second —
  // does not restyle every polygon in the project on each one.
  const parcelStyle = useMemo(() => ({
    color: '#00d4aa', weight: 1.5, fillColor: '#00d4aa',
    opacity: alpha('parcels'), fillOpacity: 0.08 * alpha('parcels'),
    dashArray: '4 4',
  }), [layerById]);
  const buildingStyle = useMemo(() => ({
    color: '#0ea5e9', weight: 2, fillColor: '#0ea5e9',
    opacity: alpha('footprints'), fillOpacity: 0.15 * alpha('footprints'),
  }), [layerById]);

  // Selecting anything opens its record. A 3D view whose click does nothing is a
  // picture of a cadastre rather than a cadastre: the geometry is the index, and the
  // record behind it is the thing a land system exists to show.
  const selectUnit = useCallback((unitId) => {
    const u = geometry.unitsById.get(unitId);
    if (!u) return;
    if (u.unit_type === 'floor' || u.unit_type === 'apartment') {
      const parent = geometry.parentOf.get(unitId);
      if (parent) setSelectedBuildingId(parent);   // keep its stack open behind it
      setActiveFloor(unitId);
    } else {
      setSelectedBuildingId(unitId);
      setActiveFloor(null);   // the previous building's floor is not this building's
    }
    setSelectedProperty(describeUnit(unitId, geometry));
  }, [geometry]);
  // What the HUD reports has to come from the scene, not from a remembered string.
  const sceneBuildingCount = sceneUnits.filter((u) => u.unit_type === 'building').length;
  const selectedBuildingLabel = sceneUnits.find((u) => u.unit_id === selectedBuildingId)?.label
    ?? selectedBuildingId;
  const selectedFloors = sceneUnits.filter(
    (u) => u.parent_unit_id === selectedBuildingId && u.unit_type === 'floor');
  const selectedFloorCount = selectedFloors.length;

  return (
    <>
      {showLayers && (
        <LayerPanel layers={layers} view={view} typeCounts={typeCounts}
                    onToggle={toggleLayer} onOpacity={setOpacity}
                    onClose={() => setShowLayers(false)} />
      )}
      <div className="map-container">
        <div className="map-tabs">
          <button className={`map-tab${view === '2d' ? ' active' : ''}`}
            onClick={() => navigate('/map-2d')}>2D Map</button>
          <span style={{ color: 'var(--text-muted)', padding: '0 4px', fontSize: 'var(--text-xs)', alignSelf: 'center' }}>|</span>
          <button className={`map-tab${view === '3d' ? ' active' : ''}`}
            onClick={() => navigate('/map-3d')}>3D Map</button>

          <div style={{ flex: 1 }} />

          {/* Map mini toolbar */}
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            {!showLayers && (
              <button className="map-floating-btn" style={{ width: 26, height: 26 }} onClick={() => setShowLayers(true)} title="Show Layers">
                <Icons.Layers style={{ width: 13, height: 13 }} />
              </button>
            )}
            {[Icons.Cursor, Icons.Crosshair, Icons.Ruler, Icons.Pencil, Icons.Move].map((Ic, i) => (
              <button key={i} className="map-floating-btn" disabled
                      title="Map tools are not built yet"
                      style={{ width: 26, height: 26 }}>
                <Ic style={{ width: 13, height: 13 }} />
              </button>
            ))}
          </div>
        </div>

        <div className="map-view">
          {view === '2d' && !bounds ? (
            // The map used to open at [12.9720, 77.5950] zoom 17 — a corner of Bengaluru
            // — whatever the project was and whether or not it held any geometry. A map
            // centred on a city the project has nothing to do with is not a neutral
            // starting point; it is a claim about where this data is.
            <div className="scene-empty">
              <div className="scene-empty-title">Nothing to place on a map yet</div>
              <div className="scene-empty-body">
                This project holds no geometry, so there is no extent to open the map at.
                A map has to be centred somewhere, and anywhere chosen for it would be a
                guess about where your data is.
                <br /><br />
                Add a parcel layer or building footprints on the Upload Data screen. The
                map opens on the project's own bounds as soon as it has some.
              </div>
            </div>
          ) : view === '2d' ? (
            <>
              {/* Framed on the project's own extent. `bounds` is what the units say,
                  so the first thing on screen is this project rather than a place. */}
              <MapContainer bounds={bounds} boundsOptions={{ padding: [40, 40] }}
                style={{ height: '100%', width: '100%' }}
                zoomControl={true} attributionControl={true}>
                {/* OpenStreetMap, which needs no key. CARTO's dark tiles now require
                    registration and serve an "API KEY REQUIRED" watermark across every
                    tile without one — not something to discover during a demo. The dark
                    treatment is a CSS filter on the tile pane instead. */}
                {drawn('basemap') && (
                  <TileLayer
                    url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                    className="basemap-dark"
                    maxZoom={19}
                    opacity={alpha('basemap')}
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  />
                )}

                <FitToProject bounds={bounds} />
                <MapReadout onChange={setReadout} />

                {/* Parcel polygons, from the project */}
                {drawn('parcels') && livePercels.map(({ unit: parcel, positions }) => (
                  <Polygon
                    key={parcel.unit_id}
                    positions={positions}
                    pathOptions={parcelStyle}
                  >
                    <Popup>
                      <div style={{ fontFamily: 'Inter, sans-serif' }}>
                        <div style={{ fontWeight: 700, color: '#00d4aa', marginBottom: 4 }}>{parcel.label}</div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>Land parcel</div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>{parcel.status}</div>
                      </div>
                    </Popup>
                  </Polygon>
                ))}

                {/* Building footprints, from the project */}
                {drawn('footprints') && liveBuildings.map(({ unit: building, positions }) => (
                  <Polygon
                    key={building.unit_id}
                    positions={positions}
                    pathOptions={buildingStyle}
                    eventHandlers={{
                      click: () => selectUnit(building.unit_id)
                    }}
                  >
                    <Popup>
                      <div style={{ fontFamily: 'Inter, sans-serif' }}>
                        <div style={{ fontWeight: 700, color: '#0ea5e9', marginBottom: 4 }}>
                          {building.label}
                        </div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>
                          {building.base_m === null || building.top_m === null
                            ? 'Height unknown'
                            : `${(building.top_m - building.base_m).toFixed(1)} m tall`}
                        </div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>{building.status}</div>
                      </div>
                    </Popup>
                  </Polygon>
                ))}
              </MapContainer>

              <div className="map-info-overlay">
                {readout?.lat == null ? (
                  <span>Move the pointer over the map for a position</span>
                ) : (
                  <>
                    <span>Lat: {readout.lat.toFixed(5)}°</span>
                    <span>Lon: {readout.lng.toFixed(5)}°</span>
                  </>
                )}
                <span>Zoom {readout?.zoom ?? '—'}</span>
                <span>
                  {readout ? `${readout.metresPerPixel.toFixed(2)} m/px` : '—'}
                </span>
              </div>
            </>
          ) : (
            <>
              <ThreeScene
                selectedBuilding={selectedBuildingId}
                onSelectBuilding={selectUnit}
                activeFloor={activeFloor}
                sceneLayers={sceneLayers}
              />
              <FloorSlider
                floors={selectedFloors}
                activeFloor={activeFloor}
                onFloorChange={(id) => (id ? selectUnit(id) : setActiveFloor(null))}
              />
              <div className="map-info-overlay">
                <span>{selectedBuildingId
                  ? `Building: ${selectedBuildingLabel}`
                  : `${sceneBuildingCount} buildings \u00b7 click one to open its floors`}</span>
                {selectedBuildingId && <span>Floors: {selectedFloorCount}</span>}
                <span>Drag to orbit · scroll to zoom</span>
              </div>
            </>
          )}
        </div>
      </div>

      {selectedProperty && (
        <PropertyPanel property={selectedProperty} onSelectUnit={selectUnit}
                       onClose={() => setSelectedProperty(null)} />
      )}
    </>
  );
}
