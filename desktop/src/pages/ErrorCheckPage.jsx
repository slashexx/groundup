import { useCallback, useEffect, useState } from 'react';
import { Icons } from '../components/Icons';
import { cadastre, findingsToRows } from '../data/cadastreApi';
import { DataSourceBanner, NothingYet, useCadastreDocument } from '../data/useCadastre';

export default function ErrorCheckPage() {
  const { live, status, error: loadError, reload } = useCadastreDocument();
  const [filter, setFilter] = useState('all');
  const [selectedError, setSelectedError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [run, setRun] = useState(null);
  // never-run | reading | ready | missing | failed. `missing` and `failed` are separate
  // states on purpose: "nobody has validated this project" and "we could not find out"
  // are different answers, and collapsing them into an empty table states the first when
  // only the second is known.
  const [runState, setRunState] = useState('reading');
  const [runError, setRunError] = useState(null);

  // The run, not the document, is what this screen reads. The document carries the same
  // findings, but it cannot say whether a run happened at all — an unvalidated project
  // and a clean one both arrive as an empty list, and only one of them is a clean bill
  // of health. `/runs/latest` answers 404 for the first.
  const loadRun = useCallback(async () => {
    setRunState('reading');
    setRunError(null);
    try {
      setRun(await cadastre.latestRun());
      setRunState('ready');
    } catch (e) {
      setRun(null);
      if (e.status === 404) {
        setRunState('missing');
      } else {
        setRunState('failed');
        setRunError(e.message);
      }
    }
  }, []);

  useEffect(() => {
    if (live) loadRun();
  }, [live, loadRun]);

  const errors = runState === 'ready' ? findingsToRows(run) : [];

  const filtered = filter === 'all' ? errors : errors.filter(e => e.type === filter);
  const errorCount = errors.filter(e => e.type === 'error').length;
  const warningCount = errors.filter(e => e.type === 'warning').length;

  // Re-running the checks is a real validation run against the project GeoPackage,
  // persisted so the approval guard has something to consult.
  async function rerun() {
    if (!live) return;
    setBusy(true);
    setActionError(null);
    try {
      await cadastre.validate();
      await loadRun();
      await reload();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(false);
    }
  }

  // A reviewer may accept a warning. An error must be fixed and revalidated — the API
  // answers 409, and that refusal is shown rather than hidden.
  async function acknowledge(row) {
    setBusy(true);
    setActionError(null);
    try {
      await cadastre.acknowledge(row.findingId, 'reviewer');
      await loadRun();
      await reload();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="error-page">
      <DataSourceBanner status={status} error={loadError} onRetry={reload} />
      {actionError && (
        <div style={{ padding: '8px 24px', fontSize: 'var(--text-sm)', color: 'var(--accent-danger, #e5484d)' }}>
          {actionError}
        </div>
      )}
      <div className="error-header">
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Error Checking
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            {runState === 'ready'
              ? `Run ${run.run_id.slice(0, 8)} · ruleset ${run.ruleset_version}`
              : 'Topology validation and data integrity checks'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div className="error-summary-counts" style={{ margin: 0 }}>
            <div className="error-count-card" style={{ padding: '6px 16px', flexDirection: 'row', gap: 8 }}>
              <span className="error-count-value errors" style={{ fontSize: 'var(--text-lg)' }}>{errorCount}</span>
              <span className="error-count-label">Errors</span>
            </div>
            <div className="error-count-card" style={{ padding: '6px 16px', flexDirection: 'row', gap: 8 }}>
              <span className="error-count-value warnings" style={{ fontSize: 'var(--text-lg)' }}>{warningCount}</span>
              <span className="error-count-label">Warnings</span>
            </div>
          </div>
          <button className="btn btn-primary" onClick={rerun} disabled={!live || busy}
            title={live ? 'Validate every unit and persist the run' : 'Requires the cadastre sidecar'}>
            <Icons.Refresh style={{ width: 14, height: 14 }} />
            {busy ? ' Running…' : ' Re-run Checks'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ padding: '8px 24px', display: 'flex', gap: 8, borderBottom: '1px solid var(--border-primary)' }}>
        {['all', 'error', 'warning'].map(f => (
          <button key={f} className={`search-filter-chip ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}>
            {f === 'all' ? `All (${errors.length})` : f === 'error' ? `Errors (${errorCount})` : `Warnings (${warningCount})`}
          </button>
        ))}
      </div>

      {/* Error Table */}
      <div className="error-table-wrapper">
        {runState === 'failed' && (
          <NothingYet title="Could not read the validation run">
            {runError} — the checks may well have run; this screen simply could not fetch
            the result, so it is not reporting one.
          </NothingYet>
        )}
        {runState === 'missing' && (
          <NothingYet title="No validation run on record">
            Nothing has been validated in this project yet, so there are no findings — which
            is not the same as there being no problems. Run the checks to find out.
          </NothingYet>
        )}
        {runState === 'ready' && filtered.length === 0 && (
          <NothingYet title={errors.length === 0 ? 'No findings' : `No ${filter}s in this run`}>
            {errors.length === 0
              ? `Run ${run.run_id.slice(0, 8)} checked every unit under ruleset ${run.ruleset_version} and raised nothing.`
              : 'Other severities are still listed under the All filter.'}
          </NothingYet>
        )}
        {runState === 'ready' && filtered.length > 0 && (
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}></th>
                <th>ID</th>
                <th>Category</th>
                <th>Description</th>
                <th>Parcel / Building</th>
                <th>Severity</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(err => (
                <tr key={err.findingId} onClick={() => setSelectedError(err)} style={{ cursor: 'pointer' }}>
                  <td>
                    <span className={`error-dot ${err.type}`} style={{ width: 8, height: 8 }} />
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 500 }}>
                    {err.id}
                  </td>
                  <td>
                    <span className="property-tag">{err.category}</span>
                  </td>
                  <td style={{ whiteSpace: 'normal', maxWidth: 400 }}>{err.description}</td>
                  <td style={{ color: 'var(--accent-secondary)' }}>{err.parcel}</td>
                  <td>
                    <span className={`status-badge ${err.severity === 'Critical' || err.severity === 'Error' ? 'error-badge' : err.severity === 'High' || err.severity === 'Warning' ? 'warning-badge' : err.severity === 'Medium' ? 'review' : 'draft'}`}>
                      {err.severity}
                    </span>
                    {err.acknowledgedBy && (
                      <span style={{ marginLeft: 6, fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                        ack. {err.acknowledgedBy}
                      </span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-ghost btn-sm" disabled title="Not built yet">
                        <Icons.Map2D style={{ width: 14, height: 14 }} />
                      </button>
                      {/* An error is never acknowledgeable — the guard is the feature, so the
                          button says so instead of offering a click that comes back 409. */}
                      {err.type === 'error' ? (
                        <button className="btn btn-ghost btn-sm" disabled
                          title="Errors cannot be acknowledged. Fix the geometry and re-run the checks.">
                          Ack
                        </button>
                      ) : err.acknowledgedBy ? null : (
                        <button className="btn btn-ghost btn-sm" title="Acknowledge this warning"
                          disabled={!live || busy}
                          onClick={(e) => { e.stopPropagation(); acknowledge(err); }}>
                          Ack
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm" disabled title="Not built yet">
                        <Icons.Pencil style={{ width: 14, height: 14 }} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </div>
    </div>
  );
}
