import React, { useCallback, useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Map2DProps, FilterState, UnitFeature } from '../../types/viewer';
import { STATUS_COLOR, STATUS_COLORS, computeBounds, buildMapFilter } from '../../utils/viewerUtils';
import {
  BASEMAP_RASTER_SOURCE_ID,
  createBlueprintStyle,
  getCartoKey,
  resolveInitialStyle,
} from '../../utils/basemapStyle';
import './Map2D.css';

export const SOURCE_ID = 'units';
export const FILL_LAYER_ID = 'units-fill';
export const OUTLINE_LAYER_ID = 'units-outline';
export const EXTRUDE_LAYER_ID = 'units-3d';

const UNIT_LAYERS = [FILL_LAYER_ID, OUTLINE_LAYER_ID, EXTRUDE_LAYER_ID] as const;

function applyFilter(
  map: maplibregl.Map,
  filter: FilterState,
  showUnderground: boolean
) {
  const expression = buildMapFilter(filter, showUnderground);
  for (const layerId of UNIT_LAYERS) {
    if (map.getLayer(layerId)) {
      map.setFilter(layerId, expression);
    }
  }
}

function applyViewMode(map: maplibregl.Map, viewMode: Map2DProps['viewMode']) {
  const is25d = viewMode === '2.5d';
  if (map.getLayer(EXTRUDE_LAYER_ID)) {
    map.setLayoutProperty(EXTRUDE_LAYER_ID, 'visibility', is25d ? 'visible' : 'none');
  }
  if (map.getLayer(FILL_LAYER_ID)) {
    map.setLayoutProperty(FILL_LAYER_ID, 'visibility', 'visible');
  }
  map.easeTo({
    pitch: is25d ? 55 : 0,
    bearing: is25d ? -18 : 0,
    duration: 400,
  });
}

function applySelection(
  map: maplibregl.Map,
  ulpin: string | null,
  units: UnitFeature[],
  didClickRef: React.MutableRefObject<string | null>
) {
  map.removeFeatureState({ source: SOURCE_ID });
  if (!ulpin) {
    didClickRef.current = null;
    return;
  }

  map.setFeatureState({ source: SOURCE_ID, id: ulpin }, { selected: true });

  if (didClickRef.current !== ulpin) {
    const feature = units.find(
      (unit) =>
        String(unit.properties?.ulpin) === String(ulpin) || String(unit.id) === String(ulpin)
    );
    if (feature) {
      const bounds = computeBounds([feature]);
      if (bounds) {
        map.fitBounds(bounds, { padding: 80, duration: 600, maxZoom: 19 });
      }
    }
  }
  didClickRef.current = null;
}

function setHoverState(
  map: maplibregl.Map,
  hoveredIdRef: React.MutableRefObject<string | null>,
  nextId: string | null
) {
  const previousId = hoveredIdRef.current;
  if (previousId && previousId !== nextId) {
    map.setFeatureState({ source: SOURCE_ID, id: previousId }, { hover: false });
  }
  if (nextId) {
    map.setFeatureState({ source: SOURCE_ID, id: nextId }, { hover: true });
  }
  hoveredIdRef.current = nextId;
  map.getCanvas().style.cursor = nextId ? 'pointer' : '';
}

function firstSymbolLayerId(map: maplibregl.Map): string | undefined {
  const layers = map.getStyle().layers ?? [];
  return layers.find((layer) => layer.type === 'symbol')?.id;
}

function addUnitsSourceAndLayers(
  map: maplibregl.Map,
  units: UnitFeature[],
  filter: FilterState,
  showUnderground: boolean,
  viewMode: Map2DProps['viewMode']
) {
  if (map.getSource(SOURCE_ID)) {
    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource;
    source.setData({ type: 'FeatureCollection', features: units });
    return;
  }

  map.addSource(SOURCE_ID, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: units },
    promoteId: 'ulpin',
  });

  const beforeId = firstSymbolLayerId(map);

  map.addLayer(
    {
      id: FILL_LAYER_ID,
      type: 'fill',
      source: SOURCE_ID,
      paint: {
        'fill-color': STATUS_COLOR,
        'fill-opacity': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          0.62,
          ['boolean', ['feature-state', 'hover'], false],
          0.5,
          0.32,
        ],
      },
    },
    beforeId
  );

  map.addLayer(
    {
      id: OUTLINE_LAYER_ID,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          '#0d6b58',
          ['boolean', ['feature-state', 'hover'], false],
          '#1c2321',
          '#334155',
        ],
        'line-width': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          3,
          ['boolean', ['feature-state', 'hover'], false],
          2.2,
          1.2,
        ],
        'line-opacity': 0.95,
      },
    },
    beforeId
  );

  map.addLayer(
    {
      id: EXTRUDE_LAYER_ID,
      type: 'fill-extrusion',
      source: SOURCE_ID,
      layout: {
        visibility: viewMode === '2.5d' ? 'visible' : 'none',
      },
      paint: {
        'fill-extrusion-base': ['coalesce', ['get', 'base_height'], 0],
        'fill-extrusion-height': ['coalesce', ['get', 'top_height'], 0],
        'fill-extrusion-color': [
          'case',
          ['==', ['get', 'unit_type'], 'underground'],
          '#5b6663',
          STATUS_COLOR,
        ],
        'fill-extrusion-opacity': 0.82,
      },
    },
    beforeId
  );

  applyFilter(map, filter, showUnderground);
  applyViewMode(map, viewMode);
}

export const Map2D: React.FC<Map2DProps> = ({
  units,
  selectedUlpin,
  filter,
  showUnderground,
  viewMode,
  onSelect,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const mapReadyRef = useRef(false);
  const hoveredIdRef = useRef<string | null>(null);
  const didClickRef = useRef<string | null>(null);
  const unitsRef = useRef(units);
  const filterRef = useRef(filter);
  const showUndergroundRef = useRef(showUnderground);
  const selectedUlpinRef = useRef(selectedUlpin);
  const viewModeRef = useRef(viewMode);
  const onSelectRef = useRef(onSelect);
  const blueprintAppliedRef = useRef(false);

  const [basemapUnavailable, setBasemapUnavailable] = useState(false);

  useEffect(() => {
    unitsRef.current = units;
  }, [units]);
  useEffect(() => {
    filterRef.current = filter;
  }, [filter]);
  useEffect(() => {
    showUndergroundRef.current = showUnderground;
  }, [showUnderground]);
  useEffect(() => {
    selectedUlpinRef.current = selectedUlpin;
  }, [selectedUlpin]);
  useEffect(() => {
    viewModeRef.current = viewMode;
  }, [viewMode]);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const fitToData = useCallback(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    const bounds = computeBounds(unitsRef.current);
    if (!bounds) return;
    map.fitBounds(bounds, { padding: 72, duration: 600, maxZoom: 19 });
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;

    const initialBounds = computeBounds(unitsRef.current);
    const cartoKey = getCartoKey();
    if (!cartoKey) {
      setBasemapUnavailable(true);
    }

    const map = new maplibregl.Map({
      container,
      style: resolveInitialStyle(),
      ...(initialBounds ? { bounds: initialBounds, fitBoundsOptions: { padding: 72, maxZoom: 18 } } : {}),
      pitch: 0,
      bearing: 0,
      attributionControl: { compact: true },
    });

    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
      'top-right'
    );

    const resizeObserver = new ResizeObserver(() => {
      map.resize();
    });
    resizeObserver.observe(container);

    map.on('style.load', () => {
      addUnitsSourceAndLayers(
        map,
        unitsRef.current,
        filterRef.current,
        showUndergroundRef.current,
        viewModeRef.current
      );

      if (selectedUlpinRef.current) {
        applySelection(map, selectedUlpinRef.current, unitsRef.current, didClickRef);
      }

      const bounds = computeBounds(unitsRef.current);
      if (bounds) {
        map.fitBounds(bounds, { padding: 72, duration: 0, maxZoom: 18 });
      }

      mapReadyRef.current = true;
    });

    map.on('error', (event) => {
      const sourceId = (event as { sourceId?: string }).sourceId;
      if (sourceId === SOURCE_ID) return;

      if (sourceId === BASEMAP_RASTER_SOURCE_ID && !blueprintAppliedRef.current) {
        blueprintAppliedRef.current = true;
        setBasemapUnavailable(true);
        map.setStyle(createBlueprintStyle());
      }
    });

    map.on('mousemove', (event) => {
      if (!mapReadyRef.current) return;
      const features = map.queryRenderedFeatures(event.point, {
        layers: [FILL_LAYER_ID, EXTRUDE_LAYER_ID].filter((id) => Boolean(map.getLayer(id))),
      });
      const feature = features[0];
      const id = feature?.properties?.ulpin ?? feature?.id;
      setHoverState(map, hoveredIdRef, id == null ? null : String(id));
    });

    map.on('click', (event) => {
      if (!mapReadyRef.current) return;

      const features = map.queryRenderedFeatures(event.point, {
        layers: [FILL_LAYER_ID, EXTRUDE_LAYER_ID].filter((id) => Boolean(map.getLayer(id))),
      });

      if (features.length === 0) {
        didClickRef.current = null;
        onSelectRef.current(null);
        return;
      }

      const target =
        features.find((feature) => feature.properties?.unit_type !== 'parcel') ?? features[0];
      const ulpin = target.properties?.ulpin ?? target.id;
      if (ulpin == null) return;

      const selectedId = String(ulpin);
      didClickRef.current = selectedId;
      onSelectRef.current(selectedId);
    });

    return () => {
      resizeObserver.disconnect();
      mapReadyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    source?.setData({ type: 'FeatureCollection', features: units });
  }, [units]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    applyFilter(map, filter, showUnderground);
  }, [filter, showUnderground]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    applySelection(map, selectedUlpin, units, didClickRef);
  }, [selectedUlpin, units]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    applyViewMode(map, viewMode);
  }, [viewMode]);

  return (
    <div className={`map2d-root ${className ?? ''}`}>
      <div ref={containerRef} className="map2d-canvas" />

      {basemapUnavailable && (
        <div className="map2d-basemap-warn" role="status">
          Basemap unavailable
        </div>
      )}

      <div className="map2d-info">
        <div className="map2d-info-title">2D · MAPLIBRE</div>
        <div>Bengaluru cadastral overlay</div>
        <div>{units.length} units · EPSG:4326</div>
      </div>

      <div className="map2d-legend" aria-label="Status legend">
        <div className="legend-title">STATUS</div>
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <div key={status} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            {status}
          </div>
        ))}
      </div>

      <div className="map2d-toolbar">
        <button type="button" onClick={fitToData}>
          Fit to data
        </button>
      </div>
    </div>
  );
};

export default Map2D;
