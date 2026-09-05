import { useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { Icons } from '../components/Icons';
import { cadastre, SidecarUnavailable } from '../data/cadastreApi';
import { useCadastreDocument, NothingYet } from '../data/useCadastre';

// The same nine kinds the creation wizard offers, because a project does not care
// whether a file arrived at the start or an hour later. The type is chosen here rather
// than guessed from the extension: .geojson is a parcel layer or a footprint layer
// depending only on what is in it, and guessing wrong puts 910 buildings into the
// register as parcels.
const SOURCE_KINDS = [
  { id: 'parcel_map', label: 'GIS parcel layer', hint: 'Cadastral polygons. Carries the 14-character ULPIN every unit inherits.', h: 0.3, v: 0.5 },
  { id: 'footprint', label: 'Building footprints', hint: 'Building outlines, attached to the parcel holding most of each one.', h: 2.0, v: 5.0 },
  { id: 'utility', label: 'Utility lines', hint: 'Becomes an easement corridor, which may cross parcel boundaries.', h: 1.0, v: 1.0 },
  { id: 'dem', label: 'DEM — bare earth', hint: 'Ground level. Without it heights stay absent.', h: 0.2, v: 0.1 },
  { id: 'dsm', label: 'DSM — surface', hint: 'Roof level. Paired with the DEM to extrude buildings.', h: 0.2, v: 0.1 },
  { id: 'ortho', label: 'Drone imagery', hint: 'Basemap and visual evidence for review.', h: 0.2, v: 1.0 },
  { id: 'pointcloud', label: 'LiDAR point cloud', hint: 'Registered as provenance; the DEM and DSM derived from it are what get read.', h: 0.1, v: 0.1 },
  { id: 'floorplan', label: 'Building floor plan', hint: 'Interior subdivision. Uses a local datum: ground floor is 0.000.', h: 0.05, v: 0.05 },
  { id: 'control', label: 'GNSS / CORS control', hint: 'The points everything else is tied to.', h: 0.02, v: 0.03 },
];

const today = () => new Date().toISOString().slice(0, 10);

export default function UploadDataPage() {
  const { doc, live, reload } = useCadastreDocument();
  const [queued, setQueued] = useState([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const projectCrs = doc?.project?.project_crs ?? 'EPSG:32643';
  const projectDatum = doc?.project?.vertical_datum ?? 'EGM2008';

  async function pick(kind) {
    setError(null);
    let paths;
    try {
      paths = await open({ multiple: true });
    } catch {
      // Outside the desktop shell there is no file dialog. Say that, rather than
      // letting the click do nothing.
      setError('Choosing a file needs the desktop shell. Run the app with `tauri dev`.');
      return;
    }
    if (!paths) return;
    const list = Array.isArray(paths) ? paths : [paths];
    setQueued(q => [
      ...q,
      ...list.map(path => ({
        path,
        name: path.split('/').pop(),
        source_type: kind.id,
        provider: '',
        capture_date: today(),
        crs: kind.id === 'dem' || kind.id === 'dsm' ? projectCrs : 'EPSG:4326',
        vertical_datum: projectDatum,
        horizontal_accuracy_m: kind.h,
        vertical_accuracy_m: kind.v,
      })),
    ]);
  }

  function edit(i, field, value) {
    setQueued(q => q.map((s, n) => (n === i ? { ...s, [field]: value } : s)));
  }

  async function process() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await cadastre.addSources(queued.map(s => ({
        ...s,
        horizontal_accuracy_m: Number(s.horizontal_accuracy_m),
        vertical_accuracy_m: Number(s.vertical_accuracy_m),
      })));
      setResult(r);
      setQueued([]);
      await reload();
    } catch (e) {
      setError(e instanceof SidecarUnavailable
        ? 'The cadastre sidecar is not running, so nothing was added.'
        : e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Upload Data</h1>
          <p className="page-subtitle">
            Add sources to this project. Every file records its own accuracy, and every
            comparison tolerance is derived from it — under-stating accuracy is safe,
            over-stating it reports measurement noise as encroachment.
          </p>
        </div>
      </div>

      {!live && (
        <NothingYet title="Not connected to the project">
          The sidecar is not answering, so there is nowhere to put a file.
        </NothingYet>
      )}

      <div className="ai-tool-grid" style={{ marginBottom: 24 }}>
        {SOURCE_KINDS.map(kind => (
          <button key={kind.id} className="ai-tool-card" onClick={() => pick(kind)}
                  disabled={!live} style={{ textAlign: 'left', cursor: live ? 'pointer' : 'not-allowed' }}>
            <div className="ai-tool-name">{kind.label}</div>
            <div className="ai-tool-desc">{kind.hint}</div>
            {/* Nine identically-styled panels of explanatory text read as documentation.
                Without something that looks like an action, the screen never says that
                a card is the thing you click - which is how a file that had a card
                waiting for it looked like a file with nowhere to go. */}
            <div className="source-card-action">
              {live ? 'Choose file…' : 'Not connected'}
            </div>
          </button>
        ))}
      </div>

      {error && (
        <div className="page-boundary" style={{ margin: '0 0 20px' }}>
          <div className="page-boundary-message">{error}</div>
        </div>
      )}

      {result && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header"><div className="card-title">Added</div></div>
          <div className="card-body" style={{ fontSize: 13, lineHeight: 1.8 }}>
            {result.layers?.length ? <div>layers written: {result.layers.join(', ')}</div> : null}
            {result.rasters?.length ? <div>rasters registered: {result.rasters.length}</div> : null}
            {'created' in result && (
              <div>
                {result.created} new unit(s), {result.reused} already present and kept —
                the identifiers already issued against them are untouched.
              </div>
            )}
            {result.unresolved_buildings?.length ? (
              <div style={{ color: 'var(--warning, #f59e0b)' }}>
                {result.unresolved_buildings.length} building(s) sit inside no parcel and
                were left unattached rather than guessed at.
              </div>
            ) : null}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="card-title">Queued ({queued.length})</div>
          <button className="btn btn-primary btn-sm"
                  disabled={!live || busy || !queued.length}
                  onClick={process}>
            {busy ? 'Adding…' : `Add ${queued.length} to project`}
          </button>
        </div>
        <div className="card-body">
          {!queued.length ? (
            <NothingYet title="Nothing queued">
              Pick a source type above. The type is chosen, never guessed from the file
              extension — a .geojson is a parcel layer or a footprint layer depending
              only on what is inside it.
            </NothingYet>
          ) : (
            <div className="scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>File</th><th>Type</th><th>Provider</th><th>Source CRS</th>
                    <th>H&plusmn; (m)</th><th>V&plusmn; (m)</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {queued.map((s, i) => (
                    <tr key={s.path + i}>
                      <td title={s.path}>{s.name}</td>
                      <td>
                        <select className="form-input" value={s.source_type}
                                onWheel={(e) => e.currentTarget.blur()}
                                onChange={(e) => edit(i, 'source_type', e.target.value)}>
                          {SOURCE_KINDS.map(k => (
                            <option key={k.id} value={k.id}>{k.label}</option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <input className="form-input" value={s.provider}
                               placeholder="who produced it"
                               onChange={(e) => edit(i, 'provider', e.target.value)} />
                      </td>
                      <td>
                        <input className="form-input" value={s.crs}
                               onChange={(e) => edit(i, 'crs', e.target.value)} />
                      </td>
                      <td>
                        <input className="form-input" type="number" step="0.01"
                               value={s.horizontal_accuracy_m}
                               onChange={(e) => edit(i, 'horizontal_accuracy_m', e.target.value)} />
                      </td>
                      <td>
                        <input className="form-input" type="number" step="0.01"
                               value={s.vertical_accuracy_m}
                               onChange={(e) => edit(i, 'vertical_accuracy_m', e.target.value)} />
                      </td>
                      <td>
                        <button className="btn btn-ghost btn-sm"
                                onClick={() => setQueued(q => q.filter((_, n) => n !== i))}>
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
