import { useEffect, useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { Icons } from '../components/Icons';
import { SidecarUnavailable, cadastre, setProjectPath } from '../data/cadastreApi';

/**
 * Create a project from the operator's own data.
 *
 * This is the only way into the application, deliberately. There is no list of existing
 * projects to pick from, because a list of projects nobody created is a list of fiction —
 * every screen behind it would be showing numbers that came from nowhere.
 *
 * The fields are not a design; they are `contracts/inbound/p2-geopackage.md`. The
 * `project_settings` step writes that table's single row, and each source writes one row
 * of `source`, which is the table P4 derives every geometric tolerance from.
 */

/** What each source type is called in front of a person, and what it is for.
 *
 *  The keys are the sidecar's `source_type` values, checked against
 *  `GET /cadastre/source-types` on mount — a label here for a type the backend does not
 *  handle is a file the operator picks and the project silently drops.
 *
 *  `accuracy` values are the conservative end of each instrument's usual range, never the
 *  optimistic one. The contract is explicit: under-claiming accuracy is safe, because a
 *  too-tight tolerance turns ordinary measurement noise into reported encroachments and
 *  fills the review queue with false positives until reviewers stop reading it.
 */
const SOURCE_KINDS = {
  parcel_map: {
    label: 'GIS parcel layer',
    hint: 'Cadastral parcel polygons. The only source that carries the existing 14-character ULPIN every unit inherits.',
    accept: { name: 'Vector', extensions: ['geojson', 'json', 'gpkg', 'shp'] },
    accuracy: [0.30, 0.50], datum: 'EGM2008', required: true,
  },
  footprint: {
    label: 'Building footprints',
    hint: 'Building outlines. Attached to a parcel that holds more than half of each one.',
    accept: { name: 'Vector', extensions: ['geojson', 'json', 'gpkg', 'shp'] },
    accuracy: [0.30, 0.50], datum: 'EGM2008',
  },
  utility: {
    label: 'Utility lines — underground or elevated',
    hint: 'Water, sewer, power, telecom, metro, walkway. Becomes an easement corridor, which is allowed to cross parcel boundaries.',
    accept: { name: 'Vector', extensions: ['geojson', 'json', 'gpkg', 'shp'] },
    accuracy: [0.50, 0.50], datum: 'EGM2008',
  },
  dem: {
    label: 'DEM — bare-earth elevation',
    hint: 'Ground level under the buildings. Without it heights stay absent, which is FR-03 working rather than failing.',
    accept: { name: 'Raster', extensions: ['tif', 'tiff'] },
    accuracy: [0.50, 0.30], datum: 'EGM2008',
  },
  dsm: {
    label: 'DSM — surface elevation',
    hint: 'Roof level. Paired with the DEM to extrude a building and divide it into floors.',
    accept: { name: 'Raster', extensions: ['tif', 'tiff'] },
    accuracy: [0.50, 0.30], datum: 'EGM2008',
  },
  ortho: {
    label: 'Drone imagery / orthophoto',
    hint: 'Basemap and visual evidence for review.',
    accept: { name: 'Raster', extensions: ['tif', 'tiff', 'jpg', 'png'] },
    accuracy: [0.10, 0.50], datum: 'EGM2008',
  },
  pointcloud: {
    label: 'LiDAR / 3D point cloud',
    hint: 'Registered as provenance. The system reads a DEM and DSM derived from it, never the tile itself — so add those too.',
    accept: { name: 'Point cloud', extensions: ['las', 'laz'] },
    accuracy: [0.15, 0.10], datum: 'WGS84_ELLIPSOID',
  },
  floorplan: {
    label: 'Building floor plan',
    hint: 'Provenance for interior subdivision. Floor plans use a local datum: ground floor level is 0.000.',
    accept: { name: 'Plan', extensions: ['pdf', 'dxf', 'dwg', 'png', 'jpg'] },
    accuracy: [0.10, 0.10], datum: 'LOCAL_FFL',
  },
  survey_control: {
    label: 'GNSS / CORS survey control',
    hint: 'Control points the rest of the data is tied to. The most accurate thing in a project, and usually the smallest.',
    accept: { name: 'Survey', extensions: ['csv', 'txt', 'geojson', 'json'] },
    accuracy: [0.02, 0.03], datum: 'WGS84_ELLIPSOID',
  },
};

/** Projected CRS in metres. P4 does area and distance maths and must not reproject per
 *  operation, so a geographic CRS such as EPSG:4326 is not offered: degrees are not a
 *  length, and every tolerance in this system is stated in metres. */
const PROJECT_CRS = [
  ['EPSG:32643', 'UTM zone 43N — Karnataka, Maharashtra, Gujarat'],
  ['EPSG:32644', 'UTM zone 44N — Delhi, Rajasthan, MP'],
  ['EPSG:32645', 'UTM zone 45N — UP, Bihar, Nepal border'],
  ['EPSG:32646', 'UTM zone 46N — West Bengal, Sikkim'],
  ['EPSG:7755', 'India TM — national grid'],
];

const SOURCE_CRS = ['EPSG:4326', 'EPSG:32643', 'EPSG:32644', 'EPSG:32645', 'EPSG:32646', 'EPSG:7755'];
const today = () => new Date().toISOString().slice(0, 10);

const STEPS = ['Project', 'Source data', 'Review'];

export default function CreateProjectPage({ onCreated }) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [known, setKnown] = useState(null);      // source types the sidecar handles

  const [p, setP] = useState({
    name: '',
    location: '',
    db_path: '',
    project_crs: 'EPSG:32643',
    vertical_datum: 'EGM2008',
    stratum_below_limit_m: -30,
    stratum_above_limit_m: 150,
    default_plinth_offset_m: 0.6,
    ulpin_version: 'v1',
    ruleset_version: 'r1',
  });
  const [sources, setSources] = useState([]);

  /** Opening an existing project. The wizard was the only entrance, which meant a
   *  project built yesterday could only be reached by building it again over the same
   *  file - which is how it came to be overwritten. */
  const [opening, setOpening] = useState(false);

  async function openExisting() {
    setError(null);
    let picked;
    try {
      picked = await open({
        multiple: false,
        filters: [{ name: 'Cadastre project', extensions: ['gpkg'] }],
      });
    } catch (e) {
      // Same fallback the source picker already offers: a dialog that will not open is
      // not a reason to be unable to open a project.
      picked = window.prompt(`Could not open the file chooser (${e}). Paste the full path to the .gpkg:`);
      if (!picked) return;
    }
    if (!picked) return;
    const path = Array.isArray(picked) ? picked[0] : picked;
    setOpening(true);
    try {
      // Ask the sidecar what the file holds before claiming it as the active project. A
      // path that is not a project is refused here, not discovered three screens later
      // by a dashboard rendering zeroes.
      setProjectPath(path);
      const info = await cadastre.openProject(path);
      onCreated({ ...info, location: '' });
    } catch (e) {
      setProjectPath(null);
      setError(e instanceof SidecarUnavailable
        ? 'The cadastre sidecar is not running, so the project cannot be read.'
        : e.message);
    } finally {
      setOpening(false);
    }
  }

  // Ask the sidecar what it accepts rather than trusting the table above.
  useEffect(() => {
    cadastre.sourceTypes()
      .then((t) => setKnown(new Set([...Object.keys(t.vector), ...Object.keys(t.raster), ...t.register_only])))
      .catch((e) => setError(e instanceof SidecarUnavailable
        ? 'The cadastre sidecar is not running. Start it with: python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000'
        : e.message));
  }, []);

  const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });

  /** Naming the project names its file too, unless the operator has chosen one.
   *
   *  The file path used to be required with no way to fill it except the native folder
   *  dialog, so a dialog that failed left Continue disabled and nothing on screen saying
   *  why. A relative name is resolved by the sidecar against its own working directory,
   *  which is the repository root — the same place `run_chain.py` writes `pilot.gpkg`. */
  const setName = (e) => {
    const name = e.target.value;
    setP((cur) => ({
      ...cur,
      name,
      db_path: cur.db_pathTouched ? cur.db_path : `${slug(name) || 'project'}.gpkg`,
    }));
  };
  const setNum = (k) => (e) => setP({ ...p, [k]: e.target.value === '' ? '' : Number(e.target.value) });

  async function addSource(kind) {
    const spec = SOURCE_KINDS[kind];
    let picked;
    try {
      picked = await open({ multiple: true, filters: [spec.accept] });
    } catch (e) {
      setError(`Could not open the file chooser: ${e}. Paste the full path instead.`);
      return;
    }
    if (!picked) return;
    const paths = Array.isArray(picked) ? picked : [picked];
    paths.forEach((path) => addPath(path, kind));
  }

  /** Add one file by path. Shared by the native chooser and the paste field, so both
   *  produce a source row with the same defaults filled in. */
  function addPath(path, kind) {
    const spec = SOURCE_KINDS[kind];
    setSources((cur) => [...cur, {
      path,
      source_type: kind,
      name: path.split('/').pop(),
      provider: '',
      capture_date: today(),
      crs: kind === 'parcel_map' || kind === 'footprint' ? 'EPSG:4326' : p.project_crs,
      vertical_datum: spec.datum,
      horizontal_accuracy_m: spec.accuracy[0],
      vertical_accuracy_m: spec.accuracy[1],
      processing_status: 'accuracy_estimated',
    }]);
  }

  const editSource = (i, k, v) =>
    setSources((cur) => cur.map((s, n) => (n === i ? { ...s, [k]: v } : s)));
  const dropSource = (i) => setSources((cur) => cur.filter((_, n) => n !== i));

  const hasVector = sources.some((s) => ['parcel_map', 'footprint', 'utility'].includes(s.source_type));
  const canAdvance = step === 0 ? p.name.trim() && p.db_path.trim() : step === 1 ? hasVector : true;

  // Say what is missing, beside the control that is refusing to move. A disabled button
  // with no reason beside it is indistinguishable from a broken one.
  const blocker = (() => {
    if (canAdvance) return null;
    if (step === 0) {
      const need = [];
      if (!p.name.trim()) need.push('a project name');
      if (!p.db_path.trim()) need.push('a project file');
      return `Needs ${need.join(' and ')}.`;
    }
    if (step === 1) return 'Needs at least one parcel, footprint or utility layer.';
    return null;
  })();

  async function chooseDestination() {
    let path;
    try {
      path = await open({ directory: true, multiple: false });
    } catch (e) {
      setError(`Could not open the folder chooser: ${e}. Type a path instead — a bare `
               + `name like "ward-42.gpkg" is written next to the sidecar.`);
      return;
    }
    if (!path) return;
    setP((cur) => ({
      ...cur,
      db_path: `${path}/${slug(cur.name) || 'project'}.gpkg`,
      db_pathTouched: true,
    }));
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const made = await cadastre.createProject({
        db_path: p.db_path,
        project_crs: p.project_crs,
        vertical_datum: p.vertical_datum,
        stratum_below_limit_m: Number(p.stratum_below_limit_m),
        stratum_above_limit_m: Number(p.stratum_above_limit_m),
        default_plinth_offset_m: Number(p.default_plinth_offset_m),
        default_parapet_deduction_m: 0.0,
        ulpin_version: p.ulpin_version,
        ruleset_version: p.ruleset_version,
        sources: sources.map((s) => ({
          ...s,
          horizontal_accuracy_m: Number(s.horizontal_accuracy_m),
          vertical_accuracy_m: Number(s.vertical_accuracy_m),
        })),
      });
      onCreated({ ...p, ...made });
    } catch (e) {
      setError(e instanceof SidecarUnavailable
        ? 'The cadastre sidecar is not running, so nothing was created.'
        : e.message);
    } finally {
      setBusy(false);
    }
  }

  const unhandled = known ? sources.filter((s) => !known.has(s.source_type)) : [];

  return (
    <div className="project-select-page">
      <div className="project-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
            <Icons.Logo style={{ width: 28, height: 28, color: '#00d4aa' }} />
            <h1 className="project-header-title">3D ULPIN — New Project</h1>
          </div>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            A project is one ward, village or city block, and everything measured within it.
          </span>
        </div>
        <button className="btn btn-secondary" onClick={openExisting} disabled={opening}>
          {opening ? 'Opening…' : 'Open existing project…'}
        </button>
      </div>

      <div className="wizard-steps" style={{ marginBottom: 24 }}>
        {STEPS.map((label, i) => (
          <div key={label} style={{ display: 'contents' }}>
            <div className={`wizard-step ${i === step ? 'active' : ''} ${i < step ? 'complete' : ''}`}>
              <div className="wizard-step-number">{i < step ? '✓' : i + 1}</div>
              <span>{label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="wizard-step-connector" />}
          </div>
        ))}
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', marginBottom: 16, borderRadius: 6,
          background: 'var(--error-bg, #3a1f1f)', border: '1px solid var(--border-primary)',
          fontSize: 'var(--text-sm)', whiteSpace: 'pre-wrap',
        }}>{error}</div>
      )}

      <div className="wizard-content">
        {step === 0 && (
          <Section title="Project settings"
                   note="These are written once and every unit in the project inherits them.">
            <Field label="Project name" hint="A ward, village or block.">
              <input className="form-input" value={p.name} onChange={setName}
                     placeholder="e.g. Bengaluru Ward 42" />
            </Field>
            <Field label="Area of interest" hint="Free text, for the record.">
              <input className="form-input" value={p.location} onChange={set('location')}
                     placeholder="e.g. Bengaluru, Karnataka" />
            </Field>

            <Field label="Project file"
                   hint="One GeoPackage holds the whole project. It is a file on this machine — there is no server.">
              <div style={{ display: 'flex', gap: 8 }}>
                <input className="form-input" value={p.db_path}
                       onChange={(e) => setP({ ...p, db_path: e.target.value, db_pathTouched: true })}
                       placeholder="ward-42.gpkg" style={{ flex: 1 }} />
                <button className="btn btn-secondary" onClick={chooseDestination}>Browse…</button>
              </div>
            </Field>

            <Field label="Project coordinate system"
                   hint="Projected, in metres. Areas and distances are computed directly in it, so degrees are not an option.">
              <select
              onWheel={(e) => e.currentTarget.blur()} className="form-select" value={p.project_crs} onChange={set('project_crs')}>
                {PROJECT_CRS.map(([code, desc]) => (
                  <option key={code} value={code}>{code} — {desc}</option>
                ))}
              </select>
            </Field>

            <Field label="Vertical datum"
                   hint="Fixed at EGM2008. Any other spelling raises DATUM_MISMATCH on every unit in the project.">
              <input className="form-input" value="EGM2008" readOnly disabled />
            </Field>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="Stratum below ground (m)"
                     hint="How far a parcel's rights reach down, relative to its own surface.">
                <input className="form-input" type="number" step="1"
                       value={p.stratum_below_limit_m} onChange={setNum('stratum_below_limit_m')} />
              </Field>
              <Field label="Stratum above ground (m)" hint="And how far up.">
                <input className="form-input" type="number" step="1"
                       value={p.stratum_above_limit_m} onChange={setNum('stratum_above_limit_m')} />
              </Field>
            </div>

            <Field label="Default plinth offset (m)"
                   hint="Height of the platform a building sits on, subtracted before floors are divided.">
              <input className="form-input" type="number" step="0.1"
                     value={p.default_plinth_offset_m} onChange={setNum('default_plinth_offset_m')} />
            </Field>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="ULPIN version" hint="Format of the identifier this project mints.">
                <input className="form-input" value={p.ulpin_version} onChange={set('ulpin_version')} />
              </Field>
              <Field label="Ruleset version" hint="Which validation rules and thresholds apply.">
                <input className="form-input" value={p.ruleset_version} onChange={set('ruleset_version')} />
              </Field>
            </div>
          </Section>
        )}

        {step === 1 && (
          <Section title="Source data"
                   note="Every file records its own accuracy, and every comparison tolerance is derived from those numbers. Under-stating accuracy is safe; over-stating it reports measurement noise as encroachment.">
            <div className="ai-tool-grid" style={{ marginBottom: 24 }}>
              {Object.entries(SOURCE_KINDS).map(([kind, spec]) => (
                <button key={kind} className="ai-tool-card" onClick={() => addSource(kind)}
                        style={{ textAlign: 'left', cursor: 'pointer' }}>
                  <div className="ai-tool-name">
                    {spec.label}{spec.required && <span style={{ color: '#00d4aa' }}> · required</span>}
                  </div>
                  <div className="ai-tool-desc">{spec.hint}</div>
                </button>
              ))}
            </div>

            <Field label="…or paste a file path"
                   hint="Press Enter to add it. The type is guessed from the extension; correct it below if wrong.">
              <input className="form-input" placeholder="/full/path/to/parcels.geojson"
                     onKeyDown={(e) => {
                       if (e.key !== 'Enter' || !e.target.value.trim()) return;
                       const path = e.target.value.trim();
                       const ext = path.split('.').pop().toLowerCase();
                       const guess = ['tif', 'tiff'].includes(ext) ? 'dsm'
                         : ['las', 'laz'].includes(ext) ? 'pointcloud'
                           : ['pdf', 'dxf', 'dwg'].includes(ext) ? 'floorplan'
                             : 'parcel_map';
                       addPath(path, guess);
                       e.target.value = '';
                     }} />
            </Field>

            {sources.length === 0 && (
              <div className="upload-dropzone">
                <div className="upload-dropzone-title">No source data yet</div>
                <div className="upload-dropzone-subtitle">
                  Start with a GIS parcel layer. It is the only source that carries the existing
                  ULPIN, and rasters cannot create a project on their own.
                </div>
              </div>
            )}

            {sources.map((s, i) => (
              <SourceRow key={`${s.path}-${i}`} s={s} i={i} spec={SOURCE_KINDS[s.source_type]}
                         onEdit={editSource} onDrop={dropSource} />
            ))}

            {sources.length > 0 && !hasVector && (
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
                Rasters and plans are registered <em>against</em> a project; they cannot start one.
                Add a parcel layer or building footprints.
              </p>
            )}
          </Section>
        )}

        {step === 2 && (
          <Section title="Review" note="Nothing is written until you create the project.">
            <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 24px', marginBottom: 24 }}>
              <Row k="Name" v={p.name} />
              <Row k="Area" v={p.location || '—'} />
              <Row k="File" v={p.db_path} />
              <Row k="Coordinate system" v={p.project_crs} />
              <Row k="Vertical datum" v={p.vertical_datum} />
              <Row k="Stratum" v={`${p.stratum_below_limit_m} m to +${p.stratum_above_limit_m} m, relative to ground`} />
              <Row k="Plinth offset" v={`${p.default_plinth_offset_m} m`} />
              <Row k="ULPIN / ruleset" v={`${p.ulpin_version} / ${p.ruleset_version}`} />
              <Row k="Sources" v={`${sources.length}`} />
            </dl>

            {unhandled.length > 0 && (
              <p style={{ fontSize: 'var(--text-sm)' }}>
                The sidecar does not handle: {unhandled.map((s) => s.source_type).join(', ')}.
                Those files would be ignored.
              </p>
            )}

            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr><th>Type</th><th>File</th><th>Provider</th><th>Captured</th><th>CRS</th><th>H±</th><th>V±</th></tr>
                </thead>
                <tbody>
                  {sources.map((s, i) => (
                    <tr key={i}>
                      <td>{SOURCE_KINDS[s.source_type]?.label ?? s.source_type}</td>
                      <td className="truncate" title={s.path}>{s.name}</td>
                      <td>{s.provider || '—'}</td>
                      <td>{s.capture_date}</td>
                      <td>{s.crs}</td>
                      <td>{s.horizontal_accuracy_m} m</td>
                      <td>{s.vertical_accuracy_m} m</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}
      </div>

      <div className="modal-footer" style={{ marginTop: 24 }}>
        {step > 0 && (
          <button className="btn btn-ghost" onClick={() => setStep(step - 1)} disabled={busy}>Back</button>
        )}
        {step < STEPS.length - 1 ? (
          <>
            {blocker && <span className="wizard-blocker">{blocker}</span>}
            <button className="btn btn-primary" disabled={!canAdvance} onClick={() => setStep(step + 1)}>
              Continue
            </button>
          </>
        ) : (
          <button className="btn btn-primary" disabled={busy || !hasVector} onClick={create}>
            {busy ? 'Creating…' : 'Create project'}
          </button>
        )}
      </div>
    </div>
  );
}

function Section({ title, note, children }) {
  return (
    <div className="settings-section">
      <div className="settings-section-title">{title}</div>
      {note && (
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 20 }}>{note}</p>
      )}
      {children}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {children}
      {hint && (
        <span style={{ fontSize: 'var(--text-xs, 11px)', color: 'var(--text-tertiary)' }}>{hint}</span>
      )}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <>
      <dt style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>{k}</dt>
      <dd style={{ margin: 0, fontSize: 'var(--text-sm)' }}>{v}</dd>
    </>
  );
}

/** One file, with the metadata `contracts/inbound/p2-geopackage.md` requires of it. */
function SourceRow({ s, i, spec, onEdit, onDrop }) {
  const edit = (k) => (e) => onEdit(i, k, e.target.value);
  return (
    <div className="upload-file-item" style={{ display: 'block', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <div className="upload-file-name">{spec?.label ?? s.source_type}</div>
          <div className="upload-file-size truncate" title={s.path}>{s.path}</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => onDrop(i)}>Remove</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        <Field label="Name"><input className="form-input" value={s.name} onChange={edit('name')} /></Field>
        <Field label="Provider">
          <input className="form-input" value={s.provider} onChange={edit('provider')}
                 placeholder="e.g. Survey of India" />
        </Field>
        <Field label="Capture date">
          <input className="form-input" type="date" value={s.capture_date} onChange={edit('capture_date')} />
        </Field>
        <Field label="Type">
          <select
              onWheel={(e) => e.currentTarget.blur()} className="form-select" value={s.source_type}
                  onChange={(e) => onEdit(i, 'source_type', e.target.value)}>
            {Object.entries(SOURCE_KINDS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </Field>
        <Field label="Source CRS">
          <select
              onWheel={(e) => e.currentTarget.blur()} className="form-select" value={s.crs} onChange={edit('crs')}>
            {SOURCE_CRS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Horizontal accuracy (m)">
          <input className="form-input" type="number" step="0.01" min="0.01"
                 value={s.horizontal_accuracy_m} onChange={edit('horizontal_accuracy_m')} />
        </Field>
        <Field label="Vertical accuracy (m)">
          <input className="form-input" type="number" step="0.01" min="0.01"
                 value={s.vertical_accuracy_m} onChange={edit('vertical_accuracy_m')} />
        </Field>
        <Field label="Vertical datum">
          <input className="form-input" value={s.vertical_datum} onChange={edit('vertical_datum')} />
        </Field>
        <Field label="Accuracy is"
               hint="Say which. An estimate recorded as a measurement is the one that misleads.">
          <select
              onWheel={(e) => e.currentTarget.blur()} className="form-select" value={s.processing_status} onChange={edit('processing_status')}>
            <option value="accuracy_estimated">estimated</option>
            <option value="harmonized">measured / from the data sheet</option>
          </select>
        </Field>
      </div>
    </div>
  );
}
