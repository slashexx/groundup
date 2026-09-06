import { useState } from 'react';
import { Icons } from '../components/Icons';
import { NothingYet } from '../data/useCadastre';

const typeColors = {
  upload: { bg: 'var(--accent-secondary-dim)', color: 'var(--accent-secondary)', icon: Icons.Upload },
  ai: { bg: 'var(--status-processing-bg)', color: 'var(--status-processing)', icon: Icons.AI },
  edit: { bg: 'var(--status-warning-bg)', color: 'var(--status-warning)', icon: Icons.Pencil },
  validation: { bg: 'var(--status-info-bg)', color: 'var(--status-info)', icon: Icons.CheckErrors },
  approve: { bg: 'var(--status-success-bg)', color: 'var(--status-success)', icon: Icons.Check },
  create: { bg: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', icon: Icons.Create3D },
  reject: { bg: 'var(--status-error-bg)', color: 'var(--status-error)', icon: Icons.Close },
  settings: { bg: 'var(--bg-surface)', color: 'var(--text-tertiary)', icon: Icons.Settings },
  export: { bg: 'var(--accent-secondary-dim)', color: 'var(--accent-secondary)', icon: Icons.Export },
};

const filterTypes = ['All', 'upload', 'ai', 'edit', 'validation', 'approve', 'create', 'reject', 'export'];

export default function HistoryPage() {
  const [filter, setFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  // The sidecar has no history route yet, so there is nothing to list. A page of
  // plausible entries — who uploaded what, who approved which unit — is the most
  // quietly misleading thing this app could show, because an audit trail is read as
  // evidence.
  const HISTORY = [];

  const filtered = HISTORY.filter(item => {
    if (filter !== 'All' && item.type !== filter) return false;
    if (searchQuery && !item.text.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !item.user.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="history-page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            Activity History
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            Complete audit trail of all project activities
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input className="form-input" type="text" placeholder="Search history..."
            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 250 }} />
          <button className="btn btn-secondary" disabled title="Exporting the activity log is not built yet">
            <Icons.Download style={{ width: 14, height: 14 }} /> Export Log
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="search-filters" style={{ marginBottom: 24 }}>
        {filterTypes.map(f => (
          <button key={f} className={`search-filter-chip ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}>
            {f === 'All' ? `All (${HISTORY.length})` : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Timeline */}
      {filtered.length === 0 && (
        <NothingYet title="No activity trail available">
          The sidecar records who acknowledged a finding and who approved a unit, but
          exposes no route to read that back — there is no history endpoint to call. This
          page stays empty rather than reconstructing a plausible one, because an audit
          trail is read as evidence.
        </NothingYet>
      )}
      <div className="history-timeline">
        {filtered.map((item, i) => {
          const typeStyle = typeColors[item.type] || typeColors.settings;
          const TypeIcon = typeStyle.icon;
          return (
            <div key={i} style={{
              display: 'flex', gap: 16, padding: '16px 0',
              borderBottom: '1px solid var(--border-primary)'
            }}>
              <div style={{
                width: 40, height: 40, borderRadius: 'var(--radius-md)',
                background: typeStyle.bg, display: 'flex', alignItems: 'center',
                justifyContent: 'center', flexShrink: 0
              }}>
                <TypeIcon style={{ width: 18, height: 18, color: typeStyle.color }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                  {item.text}
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 4, fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icons.User style={{ width: 10, height: 10 }} /> {item.user}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icons.History style={{ width: 10, height: 10 }} /> {item.time}
                  </span>
                </div>
              </div>
              <span className="property-tag" style={{ alignSelf: 'flex-start' }}>
                {item.type}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
