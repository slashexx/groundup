/**
 * App.tsx — Root application shell for the P5 ULPIN Viewer
 *
 * Architecture:
 *   App (shared state owner)
 *    ├── SearchFilter  – search ULPIN, type/status chips (thin wrapper → MapLibre setFilter)
 *    ├── Map2D         – MapLibre GL JS 2D/2.5D viewer  ← PRIMARY CONTRIBUTION
 *    ├── Viewer3D      – Cesium extruded 3D viewer (unchanged)
 *    └── DetailsPanel  – data-driven inspection panel
 *
 * All data comes from src/data/units.geojson (13 authoritative features).
 */
import React, { useState, useEffect } from 'react';
import rawUnitsData from './data/units.geojson';
import type { UnitFeature, FilterState, MapViewMode } from './types/viewer';
import { Map2D } from './components/Map2D/Map2D';
import { Viewer3D } from './components/Viewer3D/Viewer3D';
import { DetailsPanel } from './components/DetailsPanel/DetailsPanel';
import { SearchFilter } from './components/SearchFilter/SearchFilter';
import { ALL_TYPES, ALL_STATUSES, STATUS_COLORS } from './utils/viewerUtils';
import './App.css';

const MIN_SLICE = -10;
const MAX_SLICE = 13;

export const App: React.FC = () => {
  const [units, setUnits] = useState<UnitFeature[]>(
    Array.isArray(rawUnitsData?.features)
      ? (rawUnitsData.features as UnitFeature[])
      : []
  );

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

  const [selectedUlpin, setSelectedUlpin] = useState<string | null>(null);

  const [filter, setFilter] = useState<FilterState>({
    types: [...ALL_TYPES],
    statuses: [...ALL_STATUSES],
  });

  const [mapViewMode, setMapViewMode] = useState<MapViewMode>('2d');

  const [sliceEnabled, setSliceEnabled] = useState(false);
  const [sliceHeight, setSliceHeight] = useState(MAX_SLICE);
  const [showUnderground, setShowUnderground] = useState(false);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>ULPIN · Pilot Area Viewer</h1>
          <span>
            P5 Integration · Bengaluru Pilot · {units.length} features · MapLibre + Cesium
          </span>
        </div>
        <SearchFilter
          units={units}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={setSelectedUlpin}
        />
      </header>

      <main className="app-main">
        <div className="pane pane-map2d">
          <Map2D
            units={units}
            selectedUlpin={selectedUlpin}
            filter={filter}
            showUnderground={showUnderground}
            viewMode={mapViewMode}
            onSelect={setSelectedUlpin}
          />
        </div>

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

        <DetailsPanel
          units={units}
          selectedUlpin={selectedUlpin}
          onSelect={setSelectedUlpin}
        />
      </main>

      <footer className="app-footer">
        <div className="map-mode-toggle" role="group" aria-label="Map view mode">
          <span className="ctl-label">Map view</span>
          <button
            type="button"
            className={`mode-btn ${mapViewMode === '2d' ? 'active' : ''}`}
            onClick={() => setMapViewMode('2d')}
          >
            2D
          </button>
          <button
            type="button"
            className={`mode-btn ${mapViewMode === '2.5d' ? 'active' : ''}`}
            onClick={() => setMapViewMode('2.5d')}
          >
            2.5D
          </button>
        </div>

        <label className="ctl">
          <input
            type="checkbox"
            checked={sliceEnabled}
            onChange={(event) => setSliceEnabled(event.target.checked)}
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
          onChange={(event) => setSliceHeight(Number(event.target.value))}
          aria-label="Slice height in metres"
        />
        <span className="ctl-value">
          {sliceEnabled ? `${sliceHeight.toFixed(1)} m` : '—'}
        </span>

        <label className="ctl">
          <input
            type="checkbox"
            checked={showUnderground}
            onChange={(event) => setShowUnderground(event.target.checked)}
          />
          Underground view
        </label>

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
