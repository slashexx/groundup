import type { ViewerUnit } from './types'
import { TYPE_LABELS, VALIDATION_LABELS } from './types'
import { VALIDATION_COLORS } from './theme'
import { ancestorsOf, childrenOf, findUnit } from './filter'

interface DetailsPanelProps {
  units: ViewerUnit[]
  selectedId: string | null
  onSelect: (unitId: string | null) => void
}

function extent(u: ViewerUnit): string {
  const { lower_limit, upper_limit, vertical_datum } = u.raw
  if (lower_limit == null || upper_limit == null) {
    return 'unknown — recorded as absent, never guessed'
  }
  return `${lower_limit.toFixed(1)} m → ${upper_limit.toFixed(1)} m ${vertical_datum} (${(
    upper_limit - lower_limit
  ).toFixed(1)} m)`
}

export function DetailsPanel({ units, selectedId, onSelect }: DetailsPanelProps) {
  const unit = findUnit(units, selectedId)
  if (!unit) {
    return (
      <aside className="p5-panel p5-panel-empty">
        <p>Click a unit in either viewer — or search a ULPIN — to inspect it.</p>
      </aside>
    )
  }

  const crumbs = ancestorsOf(units, unit.unit_id)
  const children = childrenOf(units, unit.unit_id)

  return (
    <aside className="p5-panel">
      <nav className="p5-crumbs" aria-label="Hierarchy">
        {crumbs.map((c) => (
          <button key={c.unit_id} type="button" onClick={() => onSelect(c.unit_id)}>
            {TYPE_LABELS[c.unit_type]}
          </button>
        ))}
        <span>{TYPE_LABELS[unit.unit_type]}</span>
      </nav>

      <h2 className="p5-ulpin">{unit.label}</h2>
      <div className="p5-badges">
        <span className="p5-badge">{TYPE_LABELS[unit.unit_type]}</span>
        <span className="p5-badge">{unit.status.replace('_', ' ')}</span>
        <span
          className="p5-badge"
          style={{ background: VALIDATION_COLORS[unit.validation_state], color: '#fff' }}
        >
          {VALIDATION_LABELS[unit.validation_state]}
        </span>
        {unit.dispute_state === 'contested' && (
          <span className="p5-badge" style={{ background: '#7c2d1c', color: '#fff' }}>
            contested
          </span>
        )}
      </div>

      <dl className="p5-fields">
        <dt>3D ULPIN</dt>
        <dd>{unit.ulpin ?? 'provisional — assigned at approval'}</dd>
        <dt>Vertical extent</dt>
        <dd>{extent(unit)}</dd>
        <dt>Recorded by</dt>
        <dd>
          {unit.created_by}
          {unit.confidence_score != null && ` · confidence ${Math.round(unit.confidence_score * 100)}%`}
        </dd>
        <dt>Sources</dt>
        <dd>{unit.source_ids.join(', ')}</dd>
      </dl>

      {unit.subdivided === false && (
        <p className="p5-finding p5-info">
          <strong>info</strong> No interior data — floor deliberately not subdivided into
          apartments.
        </p>
      )}
      {unit.easement && (
        <p className="p5-finding p5-info">
          <strong>info</strong> Easement corridor — may legitimately cross parcel boundaries.
        </p>
      )}

      {unit.findings.length > 0 && (
        <div className="p5-findings">
          <h3>Check results</h3>
          {unit.findings.map((f, i) => (
            <p key={i} className={`p5-finding p5-${f.severity}`}>
              <strong>{f.severity}</strong> [{f.rule_id}] {f.message}
              {f.measured_value != null && ` — measured ${f.measured_value}`}
              {f.tolerance != null && `, tolerance ${f.tolerance}`}
            </p>
          ))}
        </div>
      )}

      {children.length > 0 && (
        <div className="p5-children">
          <h3>Contains</h3>
          {children.map((c) => (
            <button key={c.unit_id} type="button" onClick={() => onSelect(c.unit_id)}>
              {c.label}
            </button>
          ))}
        </div>
      )}
    </aside>
  )
}
