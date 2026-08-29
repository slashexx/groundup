import { useEffect, useRef, useState } from 'react'
import {
  Map as MLMap,
  type GeoJSONSource,
  type MapMouseEvent,
  type MapOptions,
} from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { UnitFilter, ViewerProps, ViewerUnit } from './types'
import {
  GROUND_COLOR,
  OUTLINE_COLOR,
  PARCEL_FILL,
  SELECT_COLOR,
  UNDERGROUND_COLOR,
  UNKNOWN_COLOR,
  VALIDATION_COLORS,
} from './theme'
import { bboxOf, findUnit } from './filter'

type FilterSpec = Parameters<MLMap['setFilter']>[1]

const SOURCE = 'units'
const FILL_LAYER = 'units-fill'
const LINE_LAYER = 'units-line'

// Parcels are emitted first by toFeatureCollection, so they draw underneath.
const COLOR_EXPR = [
  'case',
  ['==', ['get', 'unit_type'], 'land_parcel'], PARCEL_FILL,
  ['==', ['get', 'unit_type'], 'underground_feature'], UNDERGROUND_COLOR,
  ['get', 'unknown_height'], UNKNOWN_COLOR,
  ['match', ['get', 'validation_state'],
    'unvalidated', VALIDATION_COLORS.unvalidated,
    'passed', VALIDATION_COLORS.passed,
    'passed_with_warnings', VALIDATION_COLORS.passed_with_warnings,
    'failed', VALIDATION_COLORS.failed,
    '#999999'],
]

// Self-authored "blueprint" style: zero external tile/glyph requests.
const BLUEPRINT_STYLE = {
  version: 8,
  sources: {
    [SOURCE]: {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
      promoteId: 'unit_id',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': GROUND_COLOR } },
    {
      id: FILL_LAYER,
      type: 'fill',
      source: SOURCE,
      paint: {
        'fill-color': COLOR_EXPR,
        'fill-opacity': [
          'case',
          ['==', ['get', 'unit_type'], 'land_parcel'], 0.35,
          ['boolean', ['feature-state', 'hover'], false], 0.85,
          0.55,
        ],
      },
    },
    {
      id: LINE_LAYER,
      type: 'line',
      source: SOURCE,
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false], SELECT_COLOR,
          OUTLINE_COLOR,
        ],
        'line-width': [
          'case',
          ['boolean', ['feature-state', 'selected'], false], 3,
          ['boolean', ['feature-state', 'hover'], false], 1.8,
          0.8,
        ],
      },
    },
  ],
} as unknown as MapOptions['style']

function toFeatureCollection(units: ViewerUnit[]): FeatureCollection {
  const ordered = [...units].sort((a, b) =>
    (a.unit_type === 'land_parcel' ? 0 : 1) - (b.unit_type === 'land_parcel' ? 0 : 1),
  )
  return {
    type: 'FeatureCollection',
    features: ordered.map((u) => ({
      type: 'Feature',
      id: u.unit_id,
      geometry: { type: 'Polygon', coordinates: [u.ring] },
      properties: {
        unit_id: u.unit_id,
        label: u.label,
        unit_type: u.unit_type,
        validation_state: u.validation_state,
        unknown_height: u.base_m == null || u.top_m == null,
      },
    })),
  }
}

function filterExpr(f: UnitFilter): FilterSpec {
  const clauses: unknown[] = [true]
  if (f.types) {
    clauses.push(['in', ['get', 'unit_type'], ['literal', f.types]])
  }
  if (f.validation) {
    clauses.push(['in', ['get', 'validation_state'], ['literal', f.validation]])
  }
  if (f.query && f.query.trim()) {
    clauses.push([
      'in',
      f.query.trim().toUpperCase(),
      ['upcase', ['concat', ['get', 'label'], ' ', ['get', 'unit_id']]],
    ])
  }
  return ['all', ...clauses] as FilterSpec
}

/**
 * 2D situational map. Overlapping volumes (stacked floors) share a footprint,
 * so a 2D click reports the topmost feature — fine for "where is it";
 * per-floor selection belongs to the 3D viewer and search.
 */
export function Map2D({ units, selectedId, filter, onSelect }: ViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const [ready, setReady] = useState(false)
  const framedRef = useRef(false)
  const hoveredRef = useRef<string | null>(null)
  const selfSelectRef = useRef<string | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    const map = new MLMap({
      container: containerRef.current!,
      attributionControl: false,
      style: BLUEPRINT_STYLE,
      center: [76.5, 12.96],
      zoom: 15,
    })

    map.on('load', () => setReady(true))

    map.on('mousemove', (e: MapMouseEvent) => {
      const hits = map.queryRenderedFeatures(e.point, { layers: [FILL_LAYER] })
      const id = (hits[0]?.id as string | undefined) ?? null
      if (hoveredRef.current && hoveredRef.current !== id) {
        map.setFeatureState({ source: SOURCE, id: hoveredRef.current }, { hover: false })
      }
      if (id) map.setFeatureState({ source: SOURCE, id }, { hover: true })
      hoveredRef.current = id
      map.getCanvas().style.cursor = id ? 'pointer' : ''
    })

    map.on('click', (e: MapMouseEvent) => {
      const hits = map.queryRenderedFeatures(e.point, { layers: [FILL_LAYER] })
      // Prefer a concrete unit over the parcel slab underneath it.
      const hit = hits.find((h) => h.properties?.unit_type !== 'land_parcel') ?? hits[0]
      const id = (hit?.id as string | undefined) ?? null
      selfSelectRef.current = id
      onSelectRef.current(id)
    })

    if (import.meta.env.DEV) (window as unknown as { __p5map?: MLMap }).__p5map = map

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      framedRef.current = false
      setReady(false)
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const source = map.getSource(SOURCE) as GeoJSONSource
    source.setData(toFeatureCollection(units))
    if (!framedRef.current && units.length > 0) {
      const bbox = bboxOf(units)
      if (bbox) map.fitBounds(bbox, { padding: 48, duration: 0 })
      framedRef.current = true
    }
  }, [units, ready])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.setFilter(FILL_LAYER, filterExpr(filter))
    map.setFilter(LINE_LAYER, filterExpr(filter))
  }, [filter, ready])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.removeFeatureState({ source: SOURCE })
    if (selectedId) {
      map.setFeatureState({ source: SOURCE, id: selectedId }, { selected: true })
      // Only move the camera for selections made elsewhere (search, 3D click).
      if (selfSelectRef.current !== selectedId) {
        const unit = findUnit(units, selectedId)
        if (unit) {
          const bbox = bboxOf([unit])
          if (bbox) map.fitBounds(bbox, { padding: 120, duration: 600, maxZoom: 18.5 })
        }
      }
    }
    selfSelectRef.current = null
  }, [selectedId, units, ready])

  return <div ref={containerRef} className="p5-map2d" style={{ width: '100%', height: '100%' }} />
}
