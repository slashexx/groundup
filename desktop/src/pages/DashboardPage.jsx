import { Icons } from '../components/Icons';
import { useNavigate } from 'react-router-dom';
import {
  mockDashboardKPIs, mockUploadStatus, mockJobs, mockErrors,
  mockRecordsByStatus, mockHistory
} from '../data/mockData';
import { dashboardCounts } from '../data/cadastreApi';
import { DataSourceBanner, useCadastreDocument } from '../data/useCadastre';

const iconMap = {
  parcel: Icons.Parcel,
  building: Icons.Building,
  unit3d: Icons.Create3D,
  underground: Icons.Underground,
  review: Icons.Review,
  warning: Icons.Warning,
};

function ProgressRing({ percent, size = 80, strokeWidth = 6 }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="progress-ring-wrapper" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke="var(--border-primary)" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke="url(#progressGrad)" strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease' }} />
        <defs>
          <linearGradient id="progressGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#00d4aa" />
            <stop offset="100%" stopColor="#0ea5e9" />
          </linearGradient>
        </defs>
      </svg>
      <div className="progress-ring-text">
        <span className="progress-ring-percent">{percent}%</span>
        <span className="progress-ring-label">Complete</span>
      </div>
    </div>
  );
}

function DonutChart({ data, total }) {
  const colors = {
    Draft: '#64748b', Processing: '#8b5cf6', 'Needs Review': '#f59e0b',
    Approved: '#10b981', Replaced: '#3b82f6', Closed: '#475569'
  };
  const entries = Object.entries(data);
  let cumulative = 0;
  const size = 100;
  const center = size / 2;
  const radius = 38;
  const innerRadius = 26;

  const paths = entries.map(([label, value]) => {
    const startAngle = (cumulative / total) * 360;
    const sliceAngle = (value / total) * 360;
    cumulative += value;
    const startRad = ((startAngle - 90) * Math.PI) / 180;
    const endRad = (((startAngle + sliceAngle) - 90) * Math.PI) / 180;
    const largeArc = sliceAngle > 180 ? 1 : 0;
    const x1 = center + radius * Math.cos(startRad);
    const y1 = center + radius * Math.sin(startRad);
    const x2 = center + radius * Math.cos(endRad);
    const y2 = center + radius * Math.sin(endRad);
    const ix1 = center + innerRadius * Math.cos(endRad);
    const iy1 = center + innerRadius * Math.sin(endRad);
    const ix2 = center + innerRadius * Math.cos(startRad);
    const iy2 = center + innerRadius * Math.sin(startRad);

    const d = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix2} ${iy2} Z`;

    return <path key={label} d={d} fill={colors[label] || '#475569'} opacity={0.85}
      style={{ transition: 'opacity 0.2s' }}
      onMouseEnter={(e) => e.target.style.opacity = 1}
      onMouseLeave={(e) => e.target.style.opacity = 0.85} />;
  });

  return (
    <div className="donut-wrapper">
      <div className="donut-chart">
        <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
          {paths}
        </svg>
        <div className="donut-center">
          <span className="donut-total">{total.toLocaleString()}</span>
          <span className="donut-label">Total</span>
        </div>
      </div>
      <div className="donut-legend">
        {entries.map(([label, value]) => (
          <div key={label} className="donut-legend-item">
            <span className="donut-legend-color" style={{ background: colors[label] }} />
            <span className="donut-legend-label">{label}</span>
            <span className="donut-legend-value">{value.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage({ project }) {
  const navigate = useNavigate();
  const { doc, live, status: loadStatus, error: loadError, reload } = useCadastreDocument();

  const counts = live && doc ? dashboardCounts(doc) : null;

  const statusData = counts
    ? {
      Draft: counts.draft,
      Processing: 0,
      'Needs Review': counts.needsReview,
      Approved: counts.approved,
      Replaced: 0,
      Closed: 0,
    }
    : {
      Draft: mockRecordsByStatus.draft,
      Processing: mockRecordsByStatus.processing,
      'Needs Review': mockRecordsByStatus.needsReview,
      Approved: mockRecordsByStatus.approved,
      Replaced: mockRecordsByStatus.replaced,
      Closed: mockRecordsByStatus.closed,
    };

  // Counted from the project document rather than written into the source. The last
  // tile has no mock equivalent: it is FR-03 made visible — units whose height is
  // genuinely unknown, which the system records as absent instead of guessing.
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
    : mockDashboardKPIs;

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
    : mockErrors.recent.map(e => ({ ...e, acknowledged: null, detected: '29 May 2025, 09:45 AM' }));

  const statusClass = (s) => {
    const map = { Completed: 'completed', 'In Progress': 'in-progress', Queued: 'queued' };
    return map[s] || 'draft';
  };

  return (
    <div className="dashboard" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, width: '100%', overflow: 'hidden', padding: '16px 0 0 0' }}>
      <DataSourceBanner status={loadStatus} error={loadError} onRetry={reload} />

      {/* KPI Cards */}
      <div className="dashboard-kpis">
        {kpis.map((kpi, i) => {
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
            <a className="list-section-view-all" onClick={() => navigate('/history')}>View All</a>
          </div>
          <table className="list-table">
            <thead>
              <tr>
                <th style={{ width: '35%' }}>Job Name</th>
                <th style={{ width: '10%' }}>Type</th>
                <th style={{ width: '20%' }}>Progress</th>
                <th style={{ width: '25%' }}>Started</th>
                <th style={{ width: '10%' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {mockJobs.map((job, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-primary)' }}>{job.name}</td>
                  <td>{job.type}</td>
                  <td>
                    <span style={{ color: job.status === 'Completed' ? 'var(--status-success)' : job.status === 'In Progress' ? 'var(--accent-primary)' : 'var(--text-tertiary)' }}>
                      {job.status === 'In Progress' ? 'In Progress' : job.status}
                    </span>
                  </td>
                  <td>{job.time}</td>
                  <td><span className="list-table-action" onClick={() => navigate('/history')}>Open</span></td>
                </tr>
              ))}
            </tbody>
          </table>
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
            <a className="list-section-view-all" onClick={() => navigate('/history')}>View All</a>
          </div>
          <table className="list-table">
            <thead>
              <tr>
                <th style={{ width: '35%' }}>Activity</th>
                <th style={{ width: '10%' }}>Module</th>
                <th style={{ width: '20%' }}>User</th>
                <th style={{ width: '25%' }}>Time</th>
                <th style={{ width: '10%' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {mockHistory.slice(0, 4).map((item, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-primary)' }}>{item.text}</td>
                  <td style={{ textTransform: 'capitalize' }}>{item.type}</td>
                  <td>{item.user}</td>
                  <td>{item.time}</td>
                  <td><span className="list-table-action" onClick={() => navigate('/history')}>Open</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ textAlign: 'center', padding: 'var(--sp-2)', borderTop: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
            <a className="list-section-view-all" style={{ fontWeight: 600 }} onClick={() => navigate('/history')}>View Full History</a>
          </div>
        </div>
      </div>
    </div>
  );
}
