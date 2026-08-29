/**
 * App.tsx — Root application shell for the P5 ULPIN Viewer
 *
 * Architecture:
 *   App (shared state owner)
 *    ├── SearchFilter  – search ULPIN, type chips, status chips
 *    ├── Map2D         – MapLibre 2D/2.5D polygon viewer  ← PRIMARY CONTRIBUTION
 *    ├── Viewer3D      – Cesium extruded 3D viewer (consumer of same state)
 *    └── DetailsPanel  – data-driven inspection panel
 *
 * All data comes from src/data/units.geojson (13 authoritative features).
 * No fabricated records, findings, hierarchy, or API calls.
 */
import React, { useState, useEffect } from 'react';
import rawUnitsData from './data/units.geojson';
import type { UnitFeature, FilterState } from './types/viewer';
import { Map2D }        from './components/Map2D/Map2D';
import { Viewer3D }     from './components/Viewer3D/Viewer3D';
import { DetailsPanel } from './components/DetailsPanel/DetailsPanel';
import { SearchFilter } from './components/SearchFilter/SearchFilter';
import { ALL_TYPES, ALL_STATUSES, STATUS_COLORS } from './utils/viewerUtils';
import './App.css';

const MIN_SLICE = -10;  // allows underground units (min base_height = -8)
const MAX_SLICE =  13;  // top of tallest building floor

export const App: React.FC = () => {
  // ── Units data — loaded from bundled GeoJSON, with offline fetch fallback ──
  const [units, setUnits] = useState<UnitFeature[]>(
    Array.isArray(rawUnitsData?.features) ? (rawUnitsData.features as UnitFeature[]) : []
  );

  // Offline fallback — fetch from public/data/pilot-area.geojson if bundled import failed
  useEffect(() => {
    if (units.length === 0) {
      fetch('/data/pilot-area.geojson')
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data?.features)) {
            setUnits(data.features as UnitFeature[]);
          }
        })
        .catch((err) => {
          console.error('[P5] Failed to load pilot-area fallback:', err);
        });
    }
  }, [units.length]);

  // ── Shared selection state ─────────────────────────────────────────────────
  const [selectedUlpin, setSelectedUlpin] = useState<string | null>(null);

  // ── Shared filter state — all types/statuses active by default ────────────
  const [filter, setFilter] = useState<FilterState>({
    types:    [...ALL_TYPES],    // parcel, building, floor, apartment, underground
    statuses: [...ALL_STATUSES], // draft, checked, approved, error
    query:    '',
  });

  // ── Floor slice controls ───────────────────────────────────────────────────
  const [sliceEnabled, setSliceEnabled] = useState(false);
  const [sliceHeight,  setSliceHeight]  = useState(MAX_SLICE);

  // ── Underground visibility ─────────────────────────────────────────────────
  // When false: B01-B1 and UTIL-01 are hidden in both Map2D and Viewer3D
  const [showUnderground, setShowUnderground] = useState(false);

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="app-title">
          <h1>3D ULPIN · Pilot Area Viewer</h1>
          <span>P5 Integration · Bengaluru Pilot · 13 features · Fully offline</span>
        </div>
        <SearchFilter
          units={units}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={setSelectedUlpin}
        />
      </header>

      {/* ── Main 3-pane grid ── */}
      <main className="app-main">
        {/* 2D MapLibre pane — PRIMARY P5 CONTRIBUTION */}
        <div className="pane">
          <div className="pane-label">2D · MapLibre</div>
          <Map2D
            units={units}
            selectedUlpin={selectedUlpin}
            filter={filter}
            showUnderground={showUnderground}
            onSelect={setSelectedUlpin}
          />
        </div>

        {/* 3D Cesium pane — consumes identical shared state */}
        <div className="pane">
          <div className="pane-label">3D · Cesium</div>
          <Viewer3D
            units={units}
            selectedUlpin={selectedUlpin}
            filter={filter}
            sliceHeight={sliceEnabled ? sliceHeight : null}
            showUnderground={showUnderground}
            onSelect={setSelectedUlpin}
          />
        </div>

        {/* Details inspection panel */}
        <DetailsPanel
          units={units}
          selectedUlpin={selectedUlpin}
          onSelect={setSelectedUlpin}
        />
      </main>

      {/* ── Footer controls ── */}
      <footer className="app-footer">
        {/* Floor slice slider — filters by base_height in both viewers */}
        <label className="ctl">
          <input
            type="checkbox"
            checked={sliceEnabled}
            onChange={(e) => setSliceEnabled(e.target.checked)}
          />
          Floor slice
        </label>
        <input
          className="ctl-slider"
          type="range"
          min={MIN_SLICE}
          max={MAX_SLICE}
          step={0.5}
          value={sliceHeight}
          disabled={!sliceEnabled}
          onChange={(e) => setSliceHeight(Number(e.target.value))}
          aria-label="Slice height in metres"
        />
        <span className="ctl-value">
          {sliceEnabled ? `${sliceHeight.toFixed(1)} m` : '—'}
        </span>

        {/* Underground toggle — shows B01-B1 and UTIL-01 in both viewers */}
        <label className="ctl">
          <input
            type="checkbox"
            checked={showUnderground}
            onChange={(e) => setShowUnderground(e.target.checked)}
          />
          Underground view
        </label>

        {/* Status legend */}
        <div className="legend">
          {Object.entries(STATUS_COLORS).map(([status, color]) => (
            <span key={status} className="legend-item">
              <i style={{ background: color }} /> {status}
            </span>
          ))}
        </div>
      </footer>
    </div>
  );
};

export default App;
