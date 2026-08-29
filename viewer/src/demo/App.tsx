import { useMemo, useState } from 'react'
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

export default function App() {
  const units = useMemo(() => fromP4Document(demoParcel as unknown as FixtureDocument), [])
  const [sliceMin, sliceMax] = useMemo(() => heightRangeOf(units), [units])

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<UnitFilter>({})
  const [sliceOn, setSliceOn] = useState(false)
  const [sliceHeight, setSliceHeight] = useState(sliceMax)
  const [showUnderground, setShowUnderground] = useState(false)

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>groundup · 3D ULPIN Viewer</h1>
          <span>demo-parcel fixture · fully offline</span>
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
