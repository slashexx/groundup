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
 * Read-only published viewer (P6). Renders the bundle exported by
 * tools/publish.mjs — never invents data: a missing or invalid bundle is an
 * explicit error state, not a silent fallback.
 */
export default function App() {
  const [load, setLoad] = useState<LoadState>({ phase: 'loading' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<UnitFilter>({})
  const [sliceOn, setSliceOn] = useState(false)
  const [sliceHeight, setSliceHeight] = useState(0)
  const [showUnderground, setShowUnderground] = useState(false)

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
        setSliceHeight(heightRangeOf(units)[1])
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
  const [sliceMin, sliceMax] = useMemo(() => heightRangeOf(units), [units])

  if (load.phase !== 'ready') {
    return (
      <div className="gate">
        {load.phase === 'loading' ? (
          <div className="gate-card">
            <h1>groundup · 3D ULPIN</h1>
            <p>Loading published record…</p>
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
  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>groundup · 3D ULPIN</h1>
          <span className="app-sub">vertical property record · read-only</span>
        </div>
        <SearchFilter
          units={units}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={setSelectedId}
        />
      </header>

      <div className="provenance" role="note">
        <span className="prov-chip prov-strong">published record</span>
        {m?.exported_at && <span className="prov-chip">exported {new Date(m.exported_at).toLocaleString()}</span>}
        <span className="prov-chip">{units.length} units</span>
        {m?.finding_count != null && <span className="prov-chip">{m.finding_count} findings</span>}
        {m?.source && <span className="prov-chip">source: {m.source}</span>}
      </div>

      <main className="app-main">
        <div className="pane">
          <div className="pane-label">2D · plan</div>
          <Map2D units={units} selectedId={selectedId} filter={filter} onSelect={setSelectedId} />
        </div>
        <div className="pane">
          <div className="pane-label">3D · volumes</div>
          <Viewer3D
            units={units}
            selectedId={selectedId}
            filter={filter}
            sliceHeight={sliceOn ? sliceHeight : null}
            showUnderground={showUnderground}
            onSelect={setSelectedId}
          />
        </div>
        <DetailsPanel units={units} selectedId={selectedId} onSelect={setSelectedId} />
      </main>

      <footer className="app-footer">
        <label className="ctl">
          <input type="checkbox" checked={sliceOn} onChange={(e) => setSliceOn(e.target.checked)} />
          Floor slice
        </label>
        <input
          className="ctl-slider"
          type="range"
          min={sliceMin}
          max={sliceMax}
          step={0.2}
          value={sliceHeight}
          disabled={!sliceOn}
          onChange={(e) => setSliceHeight(Number(e.target.value))}
          aria-label="Slice height"
        />
        <span className="ctl-value">{sliceOn ? `${sliceHeight.toFixed(1)} m` : '—'}</span>

        <label className="ctl">
          <input
            type="checkbox"
            checked={showUnderground}
            onChange={(e) => setShowUnderground(e.target.checked)}
          />
          Underground view
        </label>

        <div className="legend">
          {Object.entries(VALIDATION_COLORS).map(([state, color]) => (
            <span key={state} className="legend-item">
              <i style={{ background: color }} />{' '}
              {VALIDATION_LABELS[state as keyof typeof VALIDATION_LABELS]}
            </span>
          ))}
        </div>
      </footer>
    </div>
  )
}
