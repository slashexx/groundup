import { useNavigate } from 'react-router-dom';
import { dashboardCounts } from '../data/cadastreApi';
import { DataSourceBanner, NothingYet, useCadastreDocument } from '../data/useCadastre';

export default function DashboardPage({ project }) {
  const navigate = useNavigate();
  const { doc, live, status: loadStatus, error: loadError, reload } = useCadastreDocument();

  const counts = live && doc ? dashboardCounts(doc) : null;

  // Counted from the project document rather than written into the source. The last
  // tile is FR-03 made visible: units whose height is genuinely unknown, which the
  // system records as absent instead of guessing.
  const kpis = counts
    ? [
      { label: 'Land Parcels', value: String(counts.parcels) },
      { label: 'Buildings / Floors', value: `${counts.buildings} / ${counts.floors}` },
      { label: '3D Property Units', value: String(counts.total) },
      { label: 'Underground / Elevated', value: `${counts.underground} / ${counts.elevated}` },
      { label: 'Pending Review', value: String(counts.needsReview) },
      { label: 'Errors / Warnings', value: `${counts.errors} / ${counts.warnings}` },
      { label: 'Height Unknown', value: String(counts.unknownHeight) },
    ]
    : null;   // no document, no numbers — see the banner above the tiles

  // Errors first — the alert list is triage, and a warning above an error is noise.
  const recentAlerts = live && doc
    ? [...(doc.findings ?? [])]
      .sort((a, b) => {
        const rank = { error: 0, warning: 1, info: 2 };
        return rank[a.severity] - rank[b.severity];
      })
      .slice(0, 3)
      .map(f => ({
        text: `${f.unit_id} — ${f.message}`,
        severity: f.severity,
        acknowledged: f.acknowledged_by,
        detected: f.detected_at?.replace('T', ' ').slice(0, 16) ?? '—',
      }))
    : [];

  return (
    <div className="dashboard" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, width: '100%', overflow: 'hidden', padding: '16px 0 0 0' }}>
      <DataSourceBanner status={loadStatus} error={loadError} onRetry={reload} />

      {/* KPI Cards */}
      <div className="dashboard-kpis">
        {(kpis ?? []).map((kpi, i) => {
          return (
            <div className="kpi-card" key={i}>
              <div className="kpi-value">{kpi.value}</div>
              <div className="kpi-label">{kpi.label}</div>
            </div>
          );
        })}
      </div>

      {/* Bottom Lists */}
      <div className="dashboard-lists" style={{ minHeight: 0 }}>
        {/* Active Processing Jobs */}
        <div className="dashboard-list-section">
          <div className="list-section-header">
            <div className="list-section-title">ACTIVE PROCESSING JOBS</div>
          </div>
          {/* Five column headers over an array that is permanently empty read as "no
              jobs are running", which is a different claim from "this app cannot tell
              you". There is no job queue on the sidecar: ingest, derive, detect and
              validate are synchronous calls made from their own screens. */}
          <NothingYet title="No job queue">
            Nothing here runs in the background. Importing sources, deriving heights,
            running detection and validating are each a call made from their own screen
            and finished by the time it answers, so there is no queue to watch.
          </NothingYet>
        </div>

        {/* Recent Alerts */}
        <div className="dashboard-list-section">
          <div className="list-section-header">
            <div className="list-section-title">RECENT ALERTS</div>
            <a className="list-section-view-all" onClick={() => navigate('/errors')}>View All</a>
          </div>
          <table className="list-table">
            <thead>
              <tr>
                <th style={{ width: '35%' }}>Alert</th>
                <th style={{ width: '10%' }}>Type</th>
                <th style={{ width: '20%' }}>Status</th>
                <th style={{ width: '25%' }}>Detected On</th>
                <th style={{ width: '10%' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {recentAlerts.map((err, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-primary)' }}>{err.text}</td>
                  <td style={{ textTransform: 'capitalize' }}>{err.severity}</td>
                  <td>{err.acknowledged ? `Acknowledged by ${err.acknowledged}` : 'Open'}</td>
                  <td>{err.detected}</td>
                  <td><span className="list-table-action" onClick={() => navigate('/errors')}>Open</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recent Activity */}
        <div className="dashboard-list-section">
          <div className="list-section-header">
            <div className="list-section-title">RECENT ACTIVITY</div>
          </div>
          {/* Same reason as the job table above: an empty activity list under full
              headers claims nobody has done anything, when in fact nothing is asking.
              Filling it with plausible rows was how this dashboard came to report AI
              runs that never happened and edits by people who had never opened the
              project. */}
          <NothingYet title="No activity feed">
            The sidecar keeps no audit log to read, so there is nothing to list here.
            What each decision recorded is kept on the thing decided — an
            acknowledgement, an approval or a suggestion review carries the name of
            whoever made it, and the History screen shows the validation runs.
          </NothingYet>
          <div style={{ textAlign: 'center', padding: 'var(--sp-2)', borderTop: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
            <a className="list-section-view-all" style={{ fontWeight: 600 }} onClick={() => navigate('/history')}>View Validation History</a>
          </div>
        </div>
      </div>
    </div>
  );
}
