import { useEffect, useMemo, useState } from 'react'
import type { FixtureDocument, UnitFilter } from '../lib/index.ts'
import {
  DetailsPanel,
  fromP4Document,
  heightRangeOf,
  Map2D,
  SearchFilter,
  VALIDATION_COLORS,
  VALIDATION_LABELS,
  Viewer3D,
} from '../lib/index.ts'
// The committed fixture is the team's integration surface: 16 units, defects
// deliberately planted. Bundled at build time so the demo needs no server.
import demoParcel from '../../../contracts/fixtures/demo-parcel.json'

// Live data from P4, when a sidecar is running. Unset by default so the demo stays
// offline by construction — the fixture is bundled and nothing is fetched. Point it at
// the sidecar to render a real project instead:
//
//     VITE_CADASTRE_API=http://127.0.0.1:8000 pnpm dev
//
// The endpoint serves the same shape as the fixture, so `fromP4Document` is unchanged.
const API = import.meta.env.VITE_CADASTRE_API as string | undefined
const DB = (import.meta.env.VITE_CADASTRE_DB as string | undefined) ?? 'pilot.gpkg'

export default function App() {
  const [doc, setDoc] = useState<FixtureDocument>(demoParcel as unknown as FixtureDocument)
  const [source, setSource] = useState(API ? 'connecting…' : 'demo-parcel fixture')

  useEffect(() => {
    if (!API) return
    const url = `${API}/cadastre/document?db_path=${encodeURIComponent(DB)}`
    let live = true
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`)
        return r.json() as Promise<FixtureDocument>
      })
      .then((d) => {
        if (!live) return
        setDoc(d)
        setSource(`live · ${DB} · ${d.units.length} units`)
      })
      .catch((e: Error) => {
        // Say so rather than silently rendering the fixture as if it were the project.
        if (live) setSource(`live fetch failed (${e.message}) — showing fixture`)
      })
    return () => {
      live = false
    }
  }, [])

  const units = useMemo(() => fromP4Document(doc), [doc])
  const [sliceMin, sliceMax] = useMemo(() => heightRangeOf(units), [units])

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<UnitFilter>({})
  const [sliceOn, setSliceOn] = useState(false)
  const [sliceHeight, setSliceHeight] = useState(sliceMax)
  const [showUnderground, setShowUnderground] = useState(false)

  // A live document has a different height range from the fixture's, so the slider has
  // to follow it or it sits outside its own bounds once the fetch lands. Adjusted during
  // render rather than in an effect: an effect would paint the stale value first and
  // then trigger a second render to correct it.
  const [renderedDoc, setRenderedDoc] = useState(doc)
  if (renderedDoc !== doc) {
    setRenderedDoc(doc)
    setSliceHeight(sliceMax)
    setSelectedId(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>groundup · 3D ULPIN Viewer</h1>
          <span>{API ? source : `${source} · fully offline`}</span>
        </div>
        <SearchFilter
          units={units}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={setSelectedId}
        />
      </header>

      <main className="app-main">
        <div className="pane">
          <div className="pane-label">2D · MapLibre</div>
          <Map2D units={units} selectedId={selectedId} filter={filter} onSelect={setSelectedId} />
        </div>
        <div className="pane">
          <div className="pane-label">3D · Cesium</div>
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
