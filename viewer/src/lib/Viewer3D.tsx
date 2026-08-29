import { useEffect, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import type { Viewer3DProps, ViewerUnit } from './types'
import { GROUND_COLOR, OUTLINE_COLOR, SELECT_COLOR, unitColor } from './theme'
import { matchesFilter } from './filter'

function createOfflineViewer(container: HTMLDivElement): Cesium.Viewer {
  // No Ion token, no imagery, flat ellipsoid terrain: zero network calls.
  const viewer = new Cesium.Viewer(container, {
    baseLayer: false,
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    baseLayerPicker: false,
    geocoder: false,
    timeline: false,
    animation: false,
    sceneModePicker: false,
    homeButton: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    creditContainer: document.createElement('div'),
  })
  viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString(GROUND_COLOR)
  viewer.scene.globe.showGroundAtmosphere = false
  return viewer
}

/**
 * Display extents. Parcels render as a thin slab at ground — their legal
 * column (the full stratum) belongs in the panel, not the scene. Units with
 * unknown heights render as a 1 m marker slab in UNKNOWN_COLOR: visible,
 * clearly not real data, never a guessed height (FR-03).
 */
function displayExtent(u: ViewerUnit): [number, number] {
  if (u.unit_type === 'land_parcel') return [0, 0.2]
  if (u.base_m == null || u.top_m == null) return [0, 1]
  return [u.base_m, u.top_m]
}

function fillColor(u: ViewerUnit, selected: boolean): Cesium.Color {
  const css = selected ? SELECT_COLOR : unitColor(u)
  const alpha = selected ? 0.95 : u.unit_type === 'land_parcel' ? 0.5 : 0.85
  return Cesium.Color.fromCssColorString(css).withAlpha(alpha)
}

function unitVisible(
  u: ViewerUnit,
  { filter, sliceHeight, showUnderground }: Viewer3DProps,
): boolean {
  if (!matchesFilter(u, filter)) return false
  if (!showUnderground && u.unit_type === 'underground_feature') return false
  // Slice strategy A: hide every volume whose base is at/above the cut.
  if (sliceHeight != null && u.unit_type !== 'land_parcel' && (u.base_m ?? 0) >= sliceHeight) {
    return false
  }
  return true
}

export function Viewer3D(props: Viewer3DProps) {
  const { units, selectedId, filter, sliceHeight, showUnderground, onSelect } = props
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const [ready, setReady] = useState(false)
  const framedRef = useRef(false)
  const unitByIdRef = useRef<Map<string, ViewerUnit>>(new Map())
  const selfPickRef = useRef<string | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    const viewer = createOfflineViewer(containerRef.current!)

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction((movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      const picked = viewer.scene.pick(movement.position)
      const id =
        Cesium.defined(picked) && picked.id instanceof Cesium.Entity
          ? (picked.id.id as string)
          : null
      selfPickRef.current = id
      onSelectRef.current(id)
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    viewerRef.current = viewer
    setReady(true)
    return () => {
      handler.destroy()
      viewer.destroy()
      viewerRef.current = null
      framedRef.current = false
      setReady(false)
    }
  }, [])

  // Rebuild entities when the dataset changes.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !ready) return
    viewer.entities.removeAll()
    const index = new Map<string, ViewerUnit>()
    for (const u of units) {
      index.set(u.unit_id, u)
      const [base, top] = displayExtent(u)
      viewer.entities.add({
        id: u.unit_id,
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(
            Cesium.Cartesian3.fromDegreesArray(u.ring.flat()),
          ),
          height: base,
          extrudedHeight: top,
          material: fillColor(u, false),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString(OUTLINE_COLOR),
        },
      })
    }
    unitByIdRef.current = index
    if (!framedRef.current && units.length > 0) {
      framedRef.current = true
      viewer.zoomTo(viewer.entities).catch(() => {})
    }
  }, [units, ready])

  // Visibility: filter + slice + underground toggle in one pass.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !ready) return
    for (const entity of viewer.entities.values) {
      const u = unitByIdRef.current.get(entity.id)
      if (u) entity.show = unitVisible(u, props)
    }
    viewer.scene.requestRender()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [units, filter, sliceHeight, showUnderground, ready])

  // See-through ground so below-grade units are visible and clickable.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !ready) return
    const globe = viewer.scene.globe
    globe.translucency.enabled = showUnderground
    globe.translucency.frontFaceAlphaByDistance = new Cesium.NearFarScalar(400, 0.45, 4000, 1.0)
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = !showUnderground
  }, [showUnderground, ready])

  // Selection: recolor everything, fly to externally-made selections.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !ready) return
    for (const entity of viewer.entities.values) {
      const u = unitByIdRef.current.get(entity.id)
      if (!u || !entity.polygon) continue
      const selected = entity.id === selectedId
      entity.polygon.material = new Cesium.ColorMaterialProperty(fillColor(u, selected))
      entity.polygon.outlineColor = new Cesium.ConstantProperty(
        Cesium.Color.fromCssColorString(selected ? SELECT_COLOR : OUTLINE_COLOR),
      )
    }
    if (selectedId && selfPickRef.current !== selectedId) {
      const entity = viewer.entities.getById(selectedId)
      if (entity) {
        viewer
          .flyTo(entity, {
            duration: 1.0,
            offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-35), 140),
          })
          .catch(() => {})
      }
    }
    selfPickRef.current = null
  }, [selectedId, units, ready])

  return <div ref={containerRef} className="p5-viewer3d" style={{ width: '100%', height: '100%' }} />
}
