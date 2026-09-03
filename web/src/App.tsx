import { useEffect, useMemo, useState } from 'react'
import type { FixtureDocument, UnitFilter, ViewerUnit } from '@viewer'
import {
  DetailsPanel,
  fromP4Document,
  heightRangeOf,
  Map2D,
  SearchFilter,
  VALIDATION_COLORS,
  VALIDATION_LABELS,
  Viewer3D,
} from '@viewer'
import { Gauge } from './Gauge.tsx'

interface Manifest {
  exported_at?: string
  source?: string
  unit_count?: number
  finding_count?: number
}

type LoadState =
  | { phase: 'loading' }
  | { phase: 'ready'; units: ViewerUnit[]; manifest: Manifest | null }
  | { phase: 'error'; message: string }

/**
 * Read-only published viewer (P6). One full-bleed 3D scene — the land itself —
 * with drafting-sheet instruments floating over it. Renders the bundle exported
 * by tools/publish.mjs and never invents data: a missing or invalid bundle is
 * an explicit error state, not a silent fallback.
 */
export default function App() {
  const [load, setLoad] = useState<LoadState>({ phase: 'loading' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<UnitFilter>({})
  const [cutOn, setCutOn] = useState(false)
  const [cutHeight, setCutHeight] = useState(0)
  const [showUnderground, setShowUnderground] = useState(false)
  const [planLarge, setPlanLarge] = useState(false)

  useEffect(() => {
    const base = import.meta.env.BASE_URL
    let live = true
    Promise.all([
      fetch(`${base}data/document.json`).then(async (r) => {
        if (!r.ok) throw new Error(`document.json: HTTP ${r.status}`)
        // static hosts often answer missing files with the SPA's index.html
        const text = await r.text()
        try {
          return JSON.parse(text) as FixtureDocument
        } catch {
          throw new Error('document.json is missing or not valid JSON')
        }
      }),
      fetch(`${base}data/manifest.json`)
        .then((r) => (r.ok ? (r.json() as Promise<Manifest>) : null))
        .catch(() => null),
    ])
      .then(([doc, manifest]) => {
        if (!live) return
        if (!Array.isArray(doc.units) || doc.units.length === 0) {
          throw new Error('document.json has no units')
        }
        const units = fromP4Document(doc)
        setLoad({ phase: 'ready', units, manifest })
        setCutHeight(heightRangeOf(units)[1])
        setSelectedId(null)
      })
      .catch((e: Error) => {
        if (live) setLoad({ phase: 'error', message: e.message })
      })
    return () => {
      live = false
    }
  }, [])

  const units = load.phase === 'ready' ? load.units : []
  const [gaugeMin, gaugeMax] = useMemo(() => heightRangeOf(units), [units])
  // The query drives search (Enter selects); it must not cull the scene —
  // a record viewer keeps spatial context while highlighting the match.
  const sceneFilter = useMemo(
    () => ({ types: filter.types, validation: filter.validation }),
    [filter.types, filter.validation],
  )
  const floorMarks = useMemo(
    () =>
      [...new Set(
        units
          .filter((u) => u.unit_type === 'floor' || u.unit_type === 'apartment')
          .map((u) => u.base_m)
          .filter((b): b is number => b != null),
      )],
    [units],
  )

  if (load.phase !== 'ready') {
    return (
      <div className="gate">
        {load.phase === 'loading' ? (
          <div className="gate-card">
            <h1>groundup</h1>
            <p>Loading the published record…</p>
          </div>
        ) : (
          <div className="gate-card gate-error" role="alert">
            <h1>No published record</h1>
            <p>
              This site is a read-only view of an exported project bundle, and the bundle
              could not be loaded ({load.message}).
            </p>
            <p>
              Republish with <code>pnpm publish:fixture:deploy</code> (or{' '}
              <code>publish:live:deploy</code> against a running cadastre sidecar) from{' '}
              <code>web/</code>.
            </p>
          </div>
        )}
      </div>
    )
  }

  const m = load.manifest
  const provenance = [
    m?.exported_at ? `exported ${new Date(m.exported_at).toLocaleString()}` : null,
    `${units.length} units`,
    m?.finding_count != null ? `${m.finding_count} findings` : null,
    m?.source ? `source ${m.source}` : null,
  ]
    .filter(Boolean)
    .join('  ·  ')

  return (
    <div className="stage">
      <div className="scene">
        <Viewer3D
          units={units}
          selectedId={selectedId}
          filter={sceneFilter}
          sliceHeight={cutOn ? cutHeight : null}
          showUnderground={showUnderground}
          onSelect={setSelectedId}
        />
      </div>

      <header className="bar">
        <div className="wordmark">
          <span className="wordmark-name">groundup</span>
          <span className="wordmark-sub">3-D record of rights · read-only</span>
        </div>
        <SearchFilter
          units={units}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={setSelectedId}
        />
      </header>

      <p className="provenance">published record · {provenance}</p>

      <aside className={`plan ${planLarge ? 'large' : ''}`}>
        <div className="plan-head">
          <span className="sheet-label">plan · pilot block</span>
          <button
            type="button"
            className="plan-zoom"
            onClick={() => setPlanLarge(!planLarge)}
            aria-label={planLarge ? 'Shrink plan' : 'Enlarge plan'}
          >
            {planLarge ? '⌄' : '⌃'}
          </button>
        </div>
        <div className="plan-map">
          <Map2D units={units} selectedId={selectedId} filter={sceneFilter} onSelect={setSelectedId} />
        </div>
        <div className="plan-legend">
          {Object.entries(VALIDATION_COLORS).map(([state, color]) => (
            <span key={state} className="legend-item">
              <i style={{ background: color }} />
              {VALIDATION_LABELS[state as keyof typeof VALIDATION_LABELS]}
            </span>
          ))}
        </div>
      </aside>

      <Gauge
        min={gaugeMin}
        max={gaugeMax}
        floors={floorMarks}
        value={cutHeight}
        cutEnabled={cutOn}
        showUnderground={showUnderground}
        onValue={setCutHeight}
        onCutToggle={setCutOn}
        onUndergroundToggle={setShowUnderground}
      />

      {selectedId ? (
        <section className="record" aria-label="Record extract">
          <div className="record-head">
            <span className="sheet-label">extract · 3-D record</span>
            <button type="button" className="record-close" onClick={() => setSelectedId(null)} aria-label="Close extract">
              ×
            </button>
          </div>
          <DetailsPanel units={units} selectedId={selectedId} onSelect={setSelectedId} />
        </section>
      ) : (
        <p className="hint">select a volume in the scene — or search a ULPIN</p>
      )}

      {/* small screens: the gauge is replaced by a plain control bar */}
      <div className="mobile-bar">
        <label className="ctl">
          <input type="checkbox" checked={cutOn} onChange={(e) => setCutOn(e.target.checked)} />
          Cut
        </label>
        <input
          type="range"
          min={gaugeMin}
          max={gaugeMax}
          step={0.2}
          value={cutHeight}
          disabled={!cutOn}
          onChange={(e) => setCutHeight(Number(e.target.value))}
          aria-label="Section cut elevation"
        />
        <label className="ctl">
          <input
            type="checkbox"
            checked={showUnderground}
            onChange={(e) => setShowUnderground(e.target.checked)}
          />
          Below grade
        </label>
      </div>
    </div>
  )
}
