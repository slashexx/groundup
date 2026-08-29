/**
 * Map2D.tsx — MapLibre GL 2D/2.5D ULPIN viewer
 *
 * Fix for blank map: GeoJSON data is loaded directly in the map 'load' event
 * handler using the units ref (not via a separate effect), eliminating the
 * timing gap between empty source init and setData call.
 *
 * Key implementation decisions:
 * - Source is added imperatively in 'load', not in the style spec
 * - promoteId:'ulpin' so feature-state works with string IDs
 * - All layers added after source in 'load'
 * - fitBounds computed from actual GeoJSON coordinates on first load
 * - showUnderground + filter → setFilter on all layers
 * - selectedUlpin → setFeatureState({ selected: true })
 * - hover → setFeatureState({ hover: true })
 * - fill-extrusion uses base_height / top_height from properties
 */
import React, { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Map2DProps, UnitFeature, FilterState } from '../../types/viewer';
import {
  BG_COLOR,
  PARCEL_COLOR,
  UNDERGROUND_COLOR,
  LINE_COLOR,
  SELECTED_COLOR,
  STATUS_COLORS,
} from '../../utils/viewerUtils';

// ── Stable IDs ────────────────────────────────────────────────────────────────
const SOURCE_ID        = 'units';
const FILL_LAYER_ID    = 'units-fill';
const EXTRUDE_LAYER_ID = 'units-extrusion';
const LINE_LAYER_ID    = 'units-line';

// ── MapLibre color expressions ────────────────────────────────────────────────
const FILL_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  'case',
  ['==', ['get', 'unit_type'], 'parcel'],      PARCEL_COLOR,
  ['==', ['get', 'unit_type'], 'underground'], UNDERGROUND_COLOR,
  ['match', ['get', 'status'],
    'draft',    STATUS_COLORS.draft,
    'checked',  STATUS_COLORS.checked,
    'approved', STATUS_COLORS.approved,
    'error',    STATUS_COLORS.error,
    '#999999',
  ],
];

// ── Bounding-box helper ───────────────────────────────────────────────────────
function computeBounds(features: UnitFeature[]): maplibregl.LngLatBoundsLike | null {
  if (!features.length) return null;
  let minLng = Infinity, maxLng = -Infinity;
  let minLat = Infinity, maxLat = -Infinity;

  for (const f of features) {
    if (f.geometry?.type !== 'Polygon') continue;
    const rings = f.geometry.coordinates as number[][][];
    for (const ring of rings) {
      for (const [lng, lat] of ring) {
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
  }
  if (!isFinite(minLng)) return null;
  return [[minLng, minLat], [maxLng, maxLat]];
}

// ── Filter expression ─────────────────────────────────────────────────────────
function buildFilter(
  filter: FilterState,
  showUnderground: boolean
): maplibregl.ExpressionSpecification {
  const conds: unknown[] = [true];

  if (filter.types && filter.types.length > 0) {
    conds.push(['in', ['get', 'unit_type'], ['literal', filter.types]]);
  }
  if (filter.statuses && filter.statuses.length > 0) {
    conds.push(['in', ['get', 'status'], ['literal', filter.statuses]]);
  }
  if (filter.query?.trim()) {
    // substring match (case-folded by uppercasing both sides)
    conds.push(['in', filter.query.trim().toUpperCase(), ['upcase', ['get', 'ulpin']]]);
  }
  if (!showUnderground) {
    conds.push(['!=', ['get', 'unit_type'], 'underground']);
  }

  return ['all', ...conds] as unknown as maplibregl.ExpressionSpecification;
}

// ── Apply helpers (called from effects, keeping them outside component) ────────
function applyFilter(
  map: maplibregl.Map,
  filter: FilterState,
  showUnderground: boolean
) {
  const expr = buildFilter(filter, showUnderground);
  for (const id of [FILL_LAYER_ID, EXTRUDE_LAYER_ID, LINE_LAYER_ID]) {
    if (map.getLayer(id)) map.setFilter(id, expr);
  }
}

function applySelection(
  map: maplibregl.Map,
  ulpin: string | null,
  units: UnitFeature[],
  didClickRef: React.MutableRefObject<string | null>
) {
  map.removeFeatureState({ source: SOURCE_ID });
  if (!ulpin) return;

  map.setFeatureState({ source: SOURCE_ID, id: ulpin }, { selected: true });

  // flyTo only when selection came from outside this map (search/Cesium/hierarchy)
  if (didClickRef.current !== ulpin) {
    const feat = units.find(
      (u) => u.properties.ulpin === ulpin || u.id === ulpin
    );
    if (feat) {
      const bounds = computeBounds([feat]);
      if (bounds) {
        map.fitBounds(bounds, { padding: 100, duration: 700, maxZoom: 19 });
      }
    }
  }
  didClickRef.current = null;
}

// ── Component ─────────────────────────────────────────────────────────────────
export const Map2D: React.FC<Map2DProps> = ({
  units,
  selectedUlpin,
  filter,
  showUnderground,
  onSelect,
}) => {
  const containerRef    = useRef<HTMLDivElement | null>(null);
  const mapRef          = useRef<maplibregl.Map | null>(null);
  const mapReadyRef     = useRef(false);  // true once map 'load' has fired
  const hoveredIdRef    = useRef<string | null>(null);
  const didClickRef     = useRef<string | null>(null);
  const onSelectRef     = useRef(onSelect);
  // Keep latest props in refs so the load-event closure sees current values
  const unitsRef           = useRef(units);
  const filterRef          = useRef(filter);
  const showUndergroundRef = useRef(showUnderground);
  const selectedUlpinRef   = useRef(selectedUlpin);

  useEffect(() => { onSelectRef.current     = onSelect;       }, [onSelect]);
  useEffect(() => { unitsRef.current        = units;          }, [units]);
  useEffect(() => { filterRef.current       = filter;         }, [filter]);
  useEffect(() => { showUndergroundRef.current = showUnderground; }, [showUnderground]);
  useEffect(() => { selectedUlpinRef.current   = selectedUlpin;  }, [selectedUlpin]);

  // ── Mount: create map, add source+layers in 'load' ───────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': BG_COLOR },
          },
        ],
      },
      center:  [77.594, 12.9713],
      zoom:    16.5,
      pitch:   30,
      bearing: -10,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.on('load', () => {
      // ── Add source imperatively after load ──────────────────────────────
      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          // Load current units immediately — no blank intermediate state
          features: unitsRef.current,
        },
        promoteId: 'ulpin',  // use ulpin property as feature id for feature-state
      });

      // ── Fill layer: 2D footprints ───────────────────────────────────────
      map.addLayer({
        id: FILL_LAYER_ID,
        type: 'fill',
        source: SOURCE_ID,
        paint: {
          'fill-color': FILL_COLOR_EXPR,
          'fill-opacity': [
            'case',
            ['==', ['get', 'unit_type'], 'parcel'],     0.22,
            ['boolean', ['feature-state', 'selected'], false], 0.92,
            ['boolean', ['feature-state', 'hover'],    false], 0.82,
            0.60,
          ],
        },
      });

      // ── Extrusion layer: vertical extent via base_height/top_height ─────
      map.addLayer({
        id: EXTRUDE_LAYER_ID,
        type: 'fill-extrusion',
        source: SOURCE_ID,
        paint: {
          'fill-extrusion-color': FILL_COLOR_EXPR,
          // base: use actual base_height (can be negative for underground)
          'fill-extrusion-base': ['get', 'base_height'],
          // height: top_height (absolute, not relative — MapLibre uses abs top)
          'fill-extrusion-height': ['get', 'top_height'],
          'fill-extrusion-opacity': [
            'case',
            ['==', ['get', 'unit_type'], 'parcel'],     0.0,
            ['boolean', ['feature-state', 'selected'], false], 0.95,
            ['boolean', ['feature-state', 'hover'],    false], 0.75,
            0.60,
          ],
          'fill-extrusion-vertical-gradient': true,
        },
      });

      // ── Line layer: outlines ────────────────────────────────────────────
      map.addLayer({
        id: LINE_LAYER_ID,
        type: 'line',
        source: SOURCE_ID,
        paint: {
          'line-color': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], SELECTED_COLOR,
            LINE_COLOR,
          ],
          'line-width': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], 3.0,
            ['boolean', ['feature-state', 'hover'],    false], 1.8,
            0.8,
          ],
        },
      });

      // ── Apply current filter / selection ────────────────────────────────
      applyFilter(map, filterRef.current, showUndergroundRef.current);
      if (selectedUlpinRef.current) {
        applySelection(map, selectedUlpinRef.current, unitsRef.current, didClickRef);
      }

      // ── fitBounds to dataset ─────────────────────────────────────────────
      const bounds = computeBounds(unitsRef.current);
      if (bounds) {
        map.fitBounds(bounds, { padding: 60, duration: 0 });
      }

      mapReadyRef.current = true;
    });

    // ── Hover via feature-state ───────────────────────────────────────────
    map.on('mousemove', (e) => {
      if (!mapReadyRef.current) return;
      const features = map.queryRenderedFeatures(e.point, {
        layers: [FILL_LAYER_ID, EXTRUDE_LAYER_ID],
      });
      const currentId = (features[0]?.id as string) ?? null;

      if (hoveredIdRef.current && hoveredIdRef.current !== currentId) {
        map.setFeatureState({ source: SOURCE_ID, id: hoveredIdRef.current }, { hover: false });
      }
      if (currentId) {
        map.setFeatureState({ source: SOURCE_ID, id: currentId }, { hover: true });
      }
      hoveredIdRef.current = currentId;
      map.getCanvas().style.cursor = currentId ? 'pointer' : '';
    });

    map.on('mouseleave', FILL_LAYER_ID, () => {
      if (hoveredIdRef.current) {
        map.setFeatureState({ source: SOURCE_ID, id: hoveredIdRef.current }, { hover: false });
        hoveredIdRef.current = null;
      }
      map.getCanvas().style.cursor = '';
    });

    // ── Click → onSelect ─────────────────────────────────────────────────
    map.on('click', (e) => {
      if (!mapReadyRef.current) return;
      const features = map.queryRenderedFeatures(e.point, {
        layers: [FILL_LAYER_ID, EXTRUDE_LAYER_ID],
      });
      if (features.length === 0) {
        didClickRef.current = null;
        onSelectRef.current(null);
        return;
      }
      // Prefer non-parcel on overlapping features
      const target = features.find((f) => f.properties?.unit_type !== 'parcel') ?? features[0];
      const id = (target.id as string) ?? target.properties?.ulpin ?? null;
      didClickRef.current = id;
      onSelectRef.current(id);
    });

    mapRef.current = map;

    return () => {
      mapReadyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []); // mount once

  // ── Update GeoJSON source data ────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    const src = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (src) {
      src.setData({ type: 'FeatureCollection', features: units });
    }
  }, [units]);

  // ── Update filter (type/status/query/underground) ─────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    applyFilter(map, filter, showUnderground);
  }, [filter, showUnderground]);

  // ── Update selection highlight + camera ───────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    applySelection(map, selectedUlpin, units, didClickRef);
  }, [selectedUlpin, units]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', position: 'relative' }}
    />
  );
};

export default Map2D;
