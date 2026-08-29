import React, { useEffect, useRef, useState } from 'react';
import type { Viewer3DProps, UnitProperties, FilterState } from '../../types/viewer';
import {
  SELECTED_COLOR,
  LINE_COLOR,
  BG_COLOR,
  getUnitColorHex,
  isUnitVisible,
} from '../../utils/viewerUtils';

interface CesiumEntity {
  id: string;
  show?: boolean;
  polygon?: {
    material: unknown;
    outlineColor: unknown;
  };
}

interface CesiumViewer {
  scene: {
    canvas: HTMLCanvasElement;
    globe: {
      baseColor: unknown;
      showGroundAtmosphere: boolean;
      translucency: {
        enabled: boolean;
        frontFaceAlphaByDistance: unknown;
      };
    };
    screenSpaceCameraController: {
      enableCollisionDetection: boolean;
    };
    pick: (pos: unknown) => unknown;
    requestRender: () => void;
  };
  entities: {
    values: CesiumEntity[];
    add: (options: unknown) => CesiumEntity;
    getById: (id: string) => CesiumEntity | undefined;
    removeAll: () => void;
  };
  zoomTo: (target: unknown) => Promise<unknown>;
  flyTo: (target: unknown, options?: unknown) => Promise<unknown>;
  destroy: () => void;
  _handler?: CesiumHandler;
}

interface CesiumHandler {
  setInputAction: (callback: (movement: { position: unknown }) => void, type: number) => void;
  destroy: () => void;
}

interface CesiumGlobal {
  Viewer: new (container: HTMLElement, options?: unknown) => CesiumViewer;
  ScreenSpaceEventHandler: new (canvas: HTMLCanvasElement) => CesiumHandler;
  ScreenSpaceEventType: {
    LEFT_CLICK: number;
  };
  EllipsoidTerrainProvider: new () => unknown;
  Color: {
    fromCssColorString: (cssColor: string) => {
      withAlpha: (alpha: number) => unknown;
    };
  };
  PolygonHierarchy: new (positions: unknown) => unknown;
  Cartesian3: {
    fromDegreesArray: (coords: number[]) => unknown;
  };
  ColorMaterialProperty: new (color: unknown) => unknown;
  ConstantProperty: new (value: unknown) => unknown;
  NearFarScalar: new (near: number, nearValue: number, far: number, farValue: number) => unknown;
  HeadingPitchRange: new (heading: number, pitch: number, range: number) => unknown;
  Math: {
    toRadians: (degrees: number) => number;
  };
  defined: (value: unknown) => boolean;
  Entity: new () => CesiumEntity;
}

function getCesiumGlobal(): CesiumGlobal | null {
  if (typeof window !== 'undefined' && 'Cesium' in window) {
    return (window as unknown as { Cesium: CesiumGlobal }).Cesium;
  }
  return null;
}

function getCesiumColor(cesium: CesiumGlobal, p: UnitProperties, isSelected: boolean): unknown {
  const hex = isSelected ? SELECTED_COLOR : getUnitColorHex(p);
  const alpha = isSelected ? 0.95 : p.unit_type === 'parcel' ? 0.5 : 0.85;
  return cesium.Color.fromCssColorString(hex).withAlpha(alpha);
}

function applyVisibility(
  viewer: CesiumViewer,
  propsMap: Map<string, UnitProperties>,
  filter: FilterState,
  sliceHeight: number | null,
  showUnderground: boolean
): void {
  for (const entity of viewer.entities.values) {
    const p = propsMap.get(entity.id);
    if (p) {
      entity.show = isUnitVisible(
        p,
        filter,
        sliceHeight ?? 0,
        showUnderground
      );
    }
  }
  viewer.scene.requestRender();
}

function applySelection(
  viewer: CesiumViewer,
  cesium: CesiumGlobal,
  propsMap: Map<string, UnitProperties>,
  selectedUlpin: string | null,
  skipFlyTo: boolean
): void {
  for (const entity of viewer.entities.values) {
    const p = propsMap.get(entity.id);
    if (p && entity.polygon) {
      const isSelected = entity.id === selectedUlpin;
      entity.polygon.material = new cesium.ColorMaterialProperty(getCesiumColor(cesium, p, isSelected));
      entity.polygon.outlineColor = new cesium.ConstantProperty(
        cesium.Color.fromCssColorString(isSelected ? SELECTED_COLOR : LINE_COLOR)
      );
    }
  }

  if (selectedUlpin && !skipFlyTo) {
    const selectedEntity = viewer.entities.getById(selectedUlpin);
    if (selectedEntity) {
      viewer
        .flyTo(selectedEntity, {
          duration: 1,
          offset: new cesium.HeadingPitchRange(0, cesium.Math.toRadians(-35), 140),
        })
        .catch(() => {});
    }
  }

  viewer.scene.requestRender();
}

export const Viewer3D: React.FC<Viewer3DProps> = ({
  units,
  selectedUlpin,
  filter,
  sliceHeight,
  showUnderground,
  onSelect,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<CesiumViewer | null>(null);
  const [isReady, setIsReady] = useState(false);
  const isInitialZoomDone = useRef(false);
  const propertiesMapRef = useRef<Map<string, UnitProperties>>(new Map());
  const clickedUlpinRef = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // Initialize Cesium Viewer
  useEffect(() => {
    let checkInterval: ReturnType<typeof setInterval> | null = null;

    const initViewer = () => {
      const cesium = getCesiumGlobal();
      if (!cesium || !containerRef.current) {
        return false;
      }

      if (viewerRef.current) return true;

      try {
        const viewer = new cesium.Viewer(containerRef.current, {
          baseLayer: false,
          terrainProvider: new cesium.EllipsoidTerrainProvider(),
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
        });

        viewer.scene.globe.baseColor = cesium.Color.fromCssColorString(BG_COLOR);
        viewer.scene.globe.showGroundAtmosphere = false;

        const handler = new cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((clickEvent) => {
          const picked = viewer.scene.pick(clickEvent.position);
          const isEntity = cesium.defined(picked) && (picked as { id?: CesiumEntity }).id;
          const pickedId = isEntity ? (picked as { id: CesiumEntity }).id.id : null;
          clickedUlpinRef.current = pickedId;
          onSelectRef.current(pickedId);
        }, cesium.ScreenSpaceEventType.LEFT_CLICK);

        viewer._handler = handler;
        viewerRef.current = viewer;
        setIsReady(true);
        return true;
      } catch (err) {
        console.error('Failed to initialize Cesium Viewer:', err);
        return false;
      }
    };

    if (!initViewer()) {
      checkInterval = setInterval(() => {
        if (initViewer() && checkInterval) {
          clearInterval(checkInterval);
          checkInterval = null;
        }
      }, 200);
    }

    return () => {
      if (checkInterval) {
        clearInterval(checkInterval);
        checkInterval = null;
      }
      if (viewerRef.current) {
        if (viewerRef.current._handler) {
          viewerRef.current._handler.destroy();
        }
        viewerRef.current.destroy();
        viewerRef.current = null;
        isInitialZoomDone.current = false;
        setIsReady(false);
      }
    };
  }, []);

  // Update entities when units change
  useEffect(() => {
    const viewer = viewerRef.current;
    const cesium = getCesiumGlobal();
    if (!viewer || !cesium || !isReady) return;

    viewer.entities.removeAll();
    const propsMap = new Map<string, UnitProperties>();

    for (const unit of units) {
      const p = unit.properties;
      propsMap.set(p.ulpin, p);

      if (
        unit.geometry &&
        unit.geometry.type === 'Polygon' &&
        Array.isArray(unit.geometry.coordinates)
      ) {
        const rings = unit.geometry.coordinates as number[][][];
        const ring = rings[0];
        if (ring) {
          const flatCoords = ring.flat();

          viewer.entities.add({
            id: p.ulpin,
            polygon: {
              hierarchy: new cesium.PolygonHierarchy(
                cesium.Cartesian3.fromDegreesArray(flatCoords)
              ),
              height: p.base_height,
              extrudedHeight: p.top_height,
              material: new cesium.ColorMaterialProperty(getCesiumColor(cesium, p, false)),
              outline: true,
              outlineColor: new cesium.ConstantProperty(cesium.Color.fromCssColorString(LINE_COLOR)),
            },
          });
        }
      }
    }

    propertiesMapRef.current = propsMap;

    if (!isInitialZoomDone.current && units.length > 0) {
      isInitialZoomDone.current = true;
      viewer.zoomTo(viewer.entities).catch(() => {});
    }
  }, [units, isReady]);

  // Update entity visibility based on filters, sliceHeight, and underground view
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !isReady) return;

    applyVisibility(viewer, propertiesMapRef.current, filter, sliceHeight, showUnderground);
  }, [filter, sliceHeight, showUnderground, isReady]);

  // Update underground translucency
  useEffect(() => {
    const viewer = viewerRef.current;
    const cesium = getCesiumGlobal();
    if (!viewer || !cesium || !isReady) return;

    const globe = viewer.scene.globe;
    globe.translucency.enabled = showUnderground;
    globe.translucency.frontFaceAlphaByDistance = new cesium.NearFarScalar(400, 0.45, 4000, 1.0);
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = !showUnderground;
    viewer.scene.requestRender();
  }, [showUnderground, isReady]);

  // Update selection highlight & flyTo camera
  useEffect(() => {
    const viewer = viewerRef.current;
    const cesium = getCesiumGlobal();
    if (!viewer || !cesium || !isReady) return;

    const skipFlyTo = clickedUlpinRef.current === selectedUlpin;
    applySelection(viewer, cesium, propertiesMapRef.current, selectedUlpin, skipFlyTo);
    clickedUlpinRef.current = null;
  }, [selectedUlpin, isReady]);

  return (
    <div
      ref={containerRef}
      className={`p5-viewer3d ${className ?? ''}`}
      style={{ width: '100%', height: '100%' }}
    />
  );
};

export default Viewer3D;
