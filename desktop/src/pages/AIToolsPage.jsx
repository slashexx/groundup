import { useCallback, useEffect, useState } from 'react';
import { Icons } from '../components/Icons';
import { AI_TOOLS } from '../data/aiTools';
import { cadastre, suggestionRows } from '../data/cadastreApi';
import { DataSourceBanner, NothingYet, useCadastreDocument } from '../data/useCadastre';

const iconMap = {
  building: Icons.Building,
  height: Icons.Height,
  layers: Icons.Layers,
  scan: Icons.Scan,
  diff: Icons.Diff,
};

/** Which sidecar route each catalogue entry actually invokes.
 *
 * The mapping lives here rather than in `aiTools.js` because it is a fact about this
 * block's HTTP surface, not about what P3 offers — the catalogue would start drifting the
 * moment a route moved. A tool absent from this map has no route at all, and its button
 * says so instead of spinning for two seconds and reporting nothing, which is what it
 * used to do.
 *
 * Height estimation and floor segmentation are the same route with the guess switched on:
 * `/derive` reads registered rasters for a height range, and `estimate_floors` additionally
 * divides each envelope by an assumed storey height. Every unit that produces carries the
 * method and a low confidence, so the guess stays visible downstream.
 */
const ROUTES = {
  'building-extraction': () => cadastre.detect(),
  'height-estimation': () => cadastre.derive(false),
  'floor-segmentation': () => cadastre.derive(true),
};

const NO_ROUTE = 'The sidecar exposes no route for this operation yet, so there is nothing to run.';

/** The sidecar's own report, verbatim. Arrays are shown as counts because a list of six
 *  hundred identifiers is not a summary, and summarising them into a sentence would mean
 *  this screen deciding which of them mattered. */
function reportLines(report) {
  return Object.entries(report).map(([k, v]) => [
    k.replace(/_/g, ' '),
    Array.isArray(v) ? v.length : v === null || v === undefined ? '—' : String(v),
  ]);
}

export default function AIToolsPage() {
  const { live, status, error: loadError, reload } = useCadastreDocument();
  const [runningJob, setRunningJob] = useState(null);
  const [reports, setReports] = useState({});
  const [runErrors, setRunErrors] = useState({});
  const [results, setResults] = useState([]);
  // reading | ready | failed. An empty list is only reported as "nothing queued" once the
  // read has actually succeeded; a failed read says it failed.
  const [queueState, setQueueState] = useState('reading');
  const [queueError, setQueueError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [actionError, setActionError] = useState(null);

  const loadSuggestions = useCallback(async () => {
    setQueueState('reading');
    setQueueError(null);
    try {
      const res = await cadastre.suggestions();
      setResults(suggestionRows(res.suggestions));
      setQueueState('ready');
    } catch (e) {
      setResults([]);
      setQueueState('failed');
      setQueueError(e.message);
    }
  }, []);

  useEffect(() => {
    if (live) loadSuggestions();
  }, [live, loadSuggestions]);

  const handleRun = async (tool) => {
    const route = ROUTES[tool.id];
    if (!route) return;
    setRunningJob(tool.id);
    setRunErrors(prev => ({ ...prev, [tool.id]: null }));
    try {
      const report = await route();
      setReports(prev => ({ ...prev, [tool.id]: report }));
      await loadSuggestions();
      await reload();
    } catch (e) {
      // 503 means P3 is not installed in this environment, 422 that the project is not
      // ready for it. Both are the sidecar telling the operator what to fix, so both are
      // shown as it wrote them.
      setRunErrors(prev => ({ ...prev, [tool.id]: e.message }));
    } finally {
      setRunningJob(null);
    }
  };

  const decide = async (suggestion, state) => {
    setBusy(suggestion.id);
    setActionError(null);
    try {
      await cadastre.reviewSuggestion(suggestion.id, state, 'reviewer');
      await loadSuggestions();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(null);
    }
  };

  // Only accepted and edited suggestions become units — FR-05's whole point. Applying
  // with nothing accepted would be a no-op the operator reads as a failure.
  const acceptedCount = results.filter(r => !r.unitId && (r.status === 'accepted' || r.status === 'edited')).length;

  const applyAccepted = async () => {
    setBusy('apply');
    setActionError(null);
    try {
      const report = await cadastre.applySuggestions();
      setReports(prev => ({ ...prev, apply: report }));
      await loadSuggestions();
      await reload();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const pending = results.filter(r => r.status === 'pending').length;

  return (
    <div className="ai-page">
      <DataSourceBanner status={status} error={loadError} onRetry={reload} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            AI Processing Tools
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            Automated building extraction, height estimation, and floor segmentation
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>AI results require manual review</span>
        </div>
      </div>

      {/* AI Tool Cards */}
      <div className="ai-tool-grid">
        {AI_TOOLS.map(tool => {
          const ToolIcon = iconMap[tool.icon] || Icons.AI;
          const wired = Boolean(ROUTES[tool.id]);
          const report = reports[tool.id];
          const failure = runErrors[tool.id];
          return (
            <div className="ai-tool-card" key={tool.id}>
              <div className="ai-tool-icon">
                <ToolIcon style={{ width: 22, height: 22 }} />
              </div>
              <div className="ai-tool-name">{tool.name}</div>
              <div className="ai-tool-desc">{tool.description}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  Model {tool.modelVersion}
                </span>
                {/* No badge until something has run. A status pill on a tool nobody has
                    invoked is a claim about a run that never happened. */}
                {report && <span className="status-badge completed">Ran</span>}
              </div>

              {failure && (
                <div style={{ marginTop: 12, fontSize: 'var(--text-xs)', color: 'var(--status-error)', lineHeight: 1.5 }}>
                  {failure}
                </div>
              )}
              {report && (
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {reportLines(report).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      <span>{k}</span>
                      <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{v}</span>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ marginTop: 12 }}>
                <button
                  className="btn btn-primary btn-sm btn-full"
                  onClick={() => handleRun(tool)}
                  disabled={!wired || !live || runningJob !== null}
                  title={!wired ? NO_ROUTE : live ? 'Run this over the open project' : 'Requires the cadastre sidecar'}
                >
                  {runningJob === tool.id ? (
                    <>Processing...</>
                  ) : (
                    <><Icons.Play style={{ width: 12, height: 12 }} /> Run Analysis</>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* AI Results */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)' }}>
            AI Results — Pending Review ({pending})
          </h3>
          <button className="btn btn-primary btn-sm" onClick={applyAccepted}
            disabled={!live || acceptedCount === 0 || busy !== null}
            title={acceptedCount === 0
              ? 'Nothing is accepted. Only accepted suggestions become units.'
              : `Turn ${acceptedCount} accepted suggestion(s) into building units`}>
            <Icons.Check style={{ width: 12, height: 12 }} /> Apply {acceptedCount} Accepted
          </button>
        </div>

        {actionError && (
          <div style={{
            padding: 12, marginBottom: 12, borderRadius: 'var(--radius-md)',
            background: 'var(--status-error-bg)', color: 'var(--status-error)', fontSize: 'var(--text-sm)',
          }}>
            {actionError}
          </div>
        )}
        {reports.apply && (
          <div style={{
            padding: 12, marginBottom: 12, borderRadius: 'var(--radius-md)',
            background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)',
          }}>
            {reportLines(reports.apply).map(([k, v]) => `${k} ${v}`).join(' · ')}
          </div>
        )}

        {queueState === 'failed' && (
          <NothingYet title="Could not read the suggestion queue">
            {queueError} — there may well be suggestions waiting; this screen could not
            fetch them, so it is not claiming the queue is empty.
          </NothingYet>
        )}
        {queueState === 'ready' && results.length === 0 && (
          <NothingYet title="No suggestions queued">
            Nothing has been detected in this project yet. Run building extraction above;
            what it finds arrives here for a decision before any of it becomes a unit.
          </NothingYet>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {results.map(result => (
            <div key={result.id} style={{
              padding: '16px 20px', background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)', display: 'flex', gap: 20, alignItems: 'flex-start'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 'var(--text-md)' }}>
                    {result.kind}
                  </span>
                  {result.unitId && (
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      now unit {result.unitId}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 8 }}>
                  From raster {result.rasters.join(', ') || '—'}
                  {/* The method rides along with the count because `ndsm_division` is a
                      guess, and a floor count shown without saying how it was reached is
                      read as a measurement. */}
                  {result.attributes?.floor_count
                    ? ` · ${result.attributes.floor_count} floors (${result.attributes.floor_count_method ?? 'method not stated'})`
                    : ''}
                </div>
                <div style={{ display: 'flex', gap: 16, fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  <span>Model: {result.modelVersion}</span>
                  <span>ID: {result.short}</span>
                  {result.reviewedBy && <span>Reviewed by {result.reviewedBy}</span>}
                </div>
              </div>

              {/* Confidence */}
              <div style={{ textAlign: 'center', minWidth: 80 }}>
                {result.confidence === null ? (
                  // The contract allows a suggestion with no score. A bar at zero would
                  // read as a model that found nothing it believed in.
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No score</div>
                ) : (
                  <>
                    <div style={{
                      fontSize: 'var(--text-xl)', fontWeight: 800,
                      color: result.confidence > 90 ? 'var(--status-success)' : result.confidence > 80 ? 'var(--status-warning)' : 'var(--status-error)'
                    }}>
                      {result.confidence.toFixed(0)}%
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Confidence</div>
                    <div className="ai-confidence-bar" style={{ marginTop: 6, width: 80 }}>
                      <div className={`ai-confidence-fill ${result.confidence > 90 ? 'high' : result.confidence > 80 ? 'medium' : 'low'}`}
                        style={{ width: `${result.confidence}%` }} />
                    </div>
                  </>
                )}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 100 }}>
                {result.status === 'pending' && !result.unitId ? (
                  <>
                    <button className="btn btn-success btn-sm" disabled={!live || busy !== null}
                      onClick={() => decide(result, 'accepted')}>
                      <Icons.Check style={{ width: 12, height: 12 }} /> Accept
                    </button>
                    <button className="btn btn-secondary btn-sm" disabled
                      title="An edited suggestion must carry the corrected outline, and this app has no geometry editor to draw one.">
                      <Icons.Pencil style={{ width: 12, height: 12 }} /> Edit
                    </button>
                    <button className="btn btn-danger btn-sm" disabled={!live || busy !== null}
                      onClick={() => decide(result, 'rejected')}>
                      <Icons.Close style={{ width: 12, height: 12 }} /> Reject
                    </button>
                  </>
                ) : (
                  <span className={`status-badge ${result.status === 'accepted' || result.status === 'edited' ? 'approved' : result.status === 'rejected' ? 'rejected' : 'review'}`}>
                    {result.unitId ? 'Applied' : result.status}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
