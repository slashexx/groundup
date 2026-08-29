/**
 * DetailsPanel.tsx — Data-driven inspection panel
 *
 * Displays ALL fields from the selected GeoJSON UnitProperties:
 *   - ULPIN, unit_type, status, owner, vertical extent, source, confidence
 *   - Hierarchy breadcrumb (built from parent_ulpin chain)
 *   - Contains/children (derived from parent_ulpin of other features)
 *   - Findings (real findings[], mapped level→label, never fabricated)
 *
 * Data source: units.geojson properties only. Nothing is fabricated.
 */
import React from 'react';
import type { DetailsPanelProps } from '../../types/viewer';
import { STATUS_COLORS, getAncestors, getChildren } from '../../utils/viewerUtils';

const FINDING_LABEL: Record<string, string> = {
  error:   '🔴 Error',
  warning: '🟡 Warning',
  info:    '🔵 Info',
};

export const DetailsPanel: React.FC<DetailsPanelProps> = ({
  units,
  selectedUlpin,
  onSelect,
  className,
}) => {
  const selectedUnit = selectedUlpin
    ? units.find((u) => u.properties.ulpin === selectedUlpin || u.id === selectedUlpin)
    : null;

  // ── Empty / no-selection state ────────────────────────────────────────────
  if (!selectedUnit) {
    return (
      <aside className={`p5-panel p5-panel-empty ${className ?? ''}`}>
        <div className="p5-panel-empty-inner">
          <span className="p5-panel-empty-icon">🗺️</span>
          <p>Click a unit in either viewer — or search a ULPIN — to inspect it.</p>
          <p className="p5-panel-hint">
            Try <code>KA-BLR-0042-B02-F01</code> to see the error finding.
          </p>
        </div>
      </aside>
    );
  }

  const p        = selectedUnit.properties;
  const ancestors = getAncestors(units, p.ulpin);
  const children  = getChildren(units, p.ulpin);
  const heightExtent = p.top_height - p.base_height;
  const statusColor  = STATUS_COLORS[p.status] ?? '#64748b';

  return (
    <aside className={`p5-panel ${className ?? ''}`}>
      {/* ── Hierarchy breadcrumb ── */}
      <nav className="p5-crumbs" aria-label="Unit hierarchy">
        {ancestors.map((ancestor) => (
          <button
            key={ancestor.properties.ulpin || String(ancestor.id)}
            type="button"
            onClick={() => onSelect(ancestor.properties.ulpin)}
          >
            {ancestor.properties.unit_type}
          </button>
        ))}
        <span>{p.unit_type}</span>
      </nav>

      {/* ── ULPIN heading ── */}
      <h2 className="p5-ulpin">{p.ulpin}</h2>

      {/* ── Badges ── */}
      <div className="p5-badges">
        <span className="p5-badge">{p.unit_type}</span>
        <span
          className="p5-badge"
          style={{ background: statusColor, color: '#fff' }}
        >
          {p.status}
        </span>
      </div>

      {/* ── Core properties ── */}
      <dl className="p5-fields">
        <dt>Owner / Right holder</dt>
        <dd>{p.owner || <em>—</em>}</dd>

        <dt>Vertical extent</dt>
        <dd>
          {p.base_height.toFixed(1)} m → {p.top_height.toFixed(1)} m
          &nbsp;<span className="p5-extent-delta">({heightExtent.toFixed(1)} m</span>
          {p.base_height < 0 ? ', below grade)' : ')'}
        </dd>

        <dt>Source</dt>
        <dd>{p.source || <em>—</em>}</dd>

        <dt>Confidence</dt>
        <dd>{Math.round(p.confidence * 100)}%</dd>
      </dl>

      {/* ── Findings — from findings[] only, no fabrication ── */}
      <div className="p5-findings">
        <h3>Checks / Findings</h3>
        {p.findings && p.findings.length > 0 ? (
          p.findings.map((finding, idx) => (
            <p key={idx} className={`p5-finding p5-finding-${finding.level}`}>
              <strong>{FINDING_LABEL[finding.level] ?? finding.level}</strong>
              <br />
              {finding.msg}
            </p>
          ))
        ) : (
          <p className="p5-finding-none">✅ No findings — unit is clean.</p>
        )}
      </div>

      {/* ── Children / Contains — derived from parent_ulpin ── */}
      {children.length > 0 && (
        <div className="p5-children">
          <h3>Contains ({children.length})</h3>
          {children.map((child) => (
            <button
              key={child.properties.ulpin || String(child.id)}
              type="button"
              className="p5-child-btn"
              onClick={() => onSelect(child.properties.ulpin)}
            >
              <span className="p5-child-type">{child.properties.unit_type}</span>
              {child.properties.ulpin}
            </button>
          ))}
        </div>
      )}
    </aside>
  );
};

export default DetailsPanel;
