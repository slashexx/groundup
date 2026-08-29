import React, { useCallback, useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import type {
  Map2DProps,
  FilterState,
  UnitFeature,
} from "../../types/viewer";

import {
  STATUS_COLOR,
  STATUS_COLORS,
  computeBounds,
  buildMapFilter,
} from "../../utils/viewerUtils";

import {
  BASEMAP_RASTER_SOURCE_ID,
  createBlueprintStyle,
  getCartoKey,
  resolveInitialStyle,
} from "../../utils/basemapStyle";

import "./Map2D.css";

export const SOURCE_ID = "units";
export const FILL_LAYER_ID = "units-fill";
export const OUTLINE_LAYER_ID = "units-outline";
export const EXTRUDE_LAYER_ID = "units-3d";

const UNIT_LAYERS = [
  FILL_LAYER_ID,
  OUTLINE_LAYER_ID,
  EXTRUDE_LAYER_ID,
] as const;

/* =========================================================
   FILTER
========================================================= */

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

/* =========================================================
   VIEW MODE
========================================================= */

function applyViewMode(
  map: maplibregl.Map,
  viewMode: Map2DProps["viewMode"]
) {
  const is25d = viewMode === "2.5d";

  if (map.getLayer(EXTRUDE_LAYER_ID)) {
    map.setLayoutProperty(
      EXTRUDE_LAYER_ID,
      "visibility",
      is25d ? "visible" : "none"
    );
  }

  if (map.getLayer(FILL_LAYER_ID)) {
    map.setLayoutProperty(
      FILL_LAYER_ID,
      "visibility",
      "visible"
    );
  }

  map.easeTo({
    pitch: is25d ? 55 : 0,
    bearing: is25d ? -18 : 0,
    duration: 400,
  });
}

/* =========================================================
   SELECTION
========================================================= */

function applySelection(
  map: maplibregl.Map,
  ulpin: string | null,
  units: UnitFeature[],
  didClickRef: React.MutableRefObject<string | null>
) {
  map.removeFeatureState({
    source: SOURCE_ID,
  });

  if (!ulpin) {
    didClickRef.current = null;
    return;
  }

  map.setFeatureState(
    {
      source: SOURCE_ID,
      id: ulpin,
    },
    {
      selected: true,
    }
  );

  if (didClickRef.current !== ulpin) {
    const feature = units.find(
      (unit) =>
        String(unit.properties?.ulpin) === String(ulpin) ||
        String(unit.id) === String(ulpin)
    );

    if (feature) {
      const bounds = computeBounds([feature]);

      if (bounds) {
        map.fitBounds(bounds, {
          padding: 100,
          duration: 600,
          maxZoom: 19,
        });
      }
    }
  }

  didClickRef.current = null;
}

/* =========================================================
   HOVER
========================================================= */

function setHoverState(
  map: maplibregl.Map,
  hoveredIdRef: React.MutableRefObject<string | null>,
  nextId: string | null
) {
  const previousId = hoveredIdRef.current;

  if (previousId && previousId !== nextId) {
    map.setFeatureState(
      {
        source: SOURCE_ID,
        id: previousId,
      },
      {
        hover: false,
      }
    );
  }

  if (nextId) {
    map.setFeatureState(
      {
        source: SOURCE_ID,
        id: nextId,
      },
      {
        hover: true,
      }
    );
  }

  hoveredIdRef.current = nextId;

  map.getCanvas().style.cursor = nextId
    ? "pointer"
    : "";
}

/* =========================================================
   FIND SYMBOL LAYER
========================================================= */

function firstSymbolLayerId(
  map: maplibregl.Map
): string | undefined {
  const layers = map.getStyle().layers ?? [];

  return layers.find(
    (layer) => layer.type === "symbol"
  )?.id;
}

/* =========================================================
   ADD GEOJSON + MAP LAYERS
========================================================= */

function addUnitsSourceAndLayers(
  map: maplibregl.Map,
  units: UnitFeature[],
  filter: FilterState,
  showUnderground: boolean,
  viewMode: Map2DProps["viewMode"]
) {
  /* -------------------------------------------------------
     SOURCE ALREADY EXISTS
  ------------------------------------------------------- */

  if (map.getSource(SOURCE_ID)) {
    const source = map.getSource(
      SOURCE_ID
    ) as maplibregl.GeoJSONSource;

    source.setData({
      type: "FeatureCollection",
      features: units,
    });

    applyFilter(
      map,
      filter,
      showUnderground
    );

    applyViewMode(
      map,
      viewMode
    );

    return;
  }

  /* -------------------------------------------------------
     GEOJSON SOURCE
  ------------------------------------------------------- */

  map.addSource(SOURCE_ID, {
    type: "geojson",

    data: {
      type: "FeatureCollection",
      features: units,
    },

    promoteId: "ulpin",
  });

  const beforeId = firstSymbolLayerId(map);

  /* -------------------------------------------------------
     2D CADASTRAL POLYGONS
  ------------------------------------------------------- */

  map.addLayer(
    {
      id: FILL_LAYER_ID,
      type: "fill",
      source: SOURCE_ID,

      paint: {
        "fill-color": STATUS_COLOR,

        "fill-opacity": [
          "case",

          [
            "boolean",
            ["feature-state", "selected"],
            false,
          ],
          0.75,

          [
            "boolean",
            ["feature-state", "hover"],
            false,
          ],
          0.55,

          0.35,
        ],
      },
    },
    beforeId
  );

  /* -------------------------------------------------------
     CADASTRAL OUTLINE
  ------------------------------------------------------- */

  map.addLayer(
    {
      id: OUTLINE_LAYER_ID,
      type: "line",
      source: SOURCE_ID,

      paint: {
        "line-color": [
          "case",

          [
            "boolean",
            ["feature-state", "selected"],
            false,
          ],
          "#00c896",

          [
            "boolean",
            ["feature-state", "hover"],
            false,
          ],
          "#ffffff",

          "#263238",
        ],

        "line-width": [
          "case",

          [
            "boolean",
            ["feature-state", "selected"],
            false,
          ],
          3,

          [
            "boolean",
            ["feature-state", "hover"],
            false,
          ],
          2,

          1,
        ],

        "line-opacity": 0.95,
      },
    },
    beforeId
  );

  /* -------------------------------------------------------
     2.5D EXTRUSION
  ------------------------------------------------------- */

  map.addLayer(
    {
      id: EXTRUDE_LAYER_ID,
      type: "fill-extrusion",
      source: SOURCE_ID,

      layout: {
        visibility:
          viewMode === "2.5d"
            ? "visible"
            : "none",
      },

      paint: {
        "fill-extrusion-base": [
          "coalesce",
          ["get", "base_height"],
          0,
        ],

        "fill-extrusion-height": [
          "coalesce",
          ["get", "top_height"],
          0,
        ],

        "fill-extrusion-color": [
          "case",

          [
            "==",
            ["get", "unit_type"],
            "underground",
          ],

          "#5b6663",

          STATUS_COLOR,
        ],

        "fill-extrusion-opacity": 0.82,

        "fill-extrusion-vertical-gradient": true,
      },
    },
    beforeId
  );

  /* -------------------------------------------------------
     APPLY CURRENT STATE
  ------------------------------------------------------- */

  applyFilter(
    map,
    filter,
    showUnderground
  );

  applyViewMode(
    map,
    viewMode
  );
}

/* =========================================================
   COMPONENT
========================================================= */

export const Map2D: React.FC<Map2DProps> = ({
  units,
  selectedUlpin,
  filter,
  showUnderground,
  viewMode,
  onSelect,
  className,
}) => {
  /* =======================================================
     REFS
  ======================================================= */

  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const mapRef =
    useRef<maplibregl.Map | null>(null);

  const mapReadyRef =
    useRef(false);

  const hoveredIdRef =
    useRef<string | null>(null);

  const didClickRef =
    useRef<string | null>(null);

  const unitsRef =
    useRef<UnitFeature[]>(units);

  const filterRef =
    useRef<FilterState>(filter);

  const showUndergroundRef =
    useRef<boolean>(showUnderground);

  const selectedUlpinRef =
    useRef<string | null>(selectedUlpin);

  const viewModeRef =
    useRef<Map2DProps["viewMode"]>(viewMode);

  const onSelectRef =
    useRef(onSelect);

  const blueprintAppliedRef =
    useRef(false);

  /* =======================================================
     STATE
  ======================================================= */

  const [
    basemapUnavailable,
    setBasemapUnavailable,
  ] = useState(false);

  /* =======================================================
     KEEP REFS UPDATED
  ======================================================= */

  useEffect(() => {
    unitsRef.current = units;
  }, [units]);

  useEffect(() => {
    filterRef.current = filter;
  }, [filter]);

  useEffect(() => {
    showUndergroundRef.current =
      showUnderground;
  }, [showUnderground]);

  useEffect(() => {
    selectedUlpinRef.current =
      selectedUlpin;
  }, [selectedUlpin]);

  useEffect(() => {
    viewModeRef.current =
      viewMode;
  }, [viewMode]);

  useEffect(() => {
    onSelectRef.current =
      onSelect;
  }, [onSelect]);

  /* =======================================================
     FIT TO DATA
  ======================================================= */

  const fitToData = useCallback(() => {
    const map = mapRef.current;

    if (
      !map ||
      !mapReadyRef.current
    ) {
      return;
    }

    const bounds = computeBounds(
      unitsRef.current
    );

    if (!bounds) {
      console.warn(
        "Map2D: unable to calculate GeoJSON bounds."
      );

      return;
    }

    map.fitBounds(bounds, {
      padding: 90,
      duration: 600,
      maxZoom: 19,
    });
  }, []);

  /* =======================================================
     INITIALIZE MAP
  ======================================================= */

  useEffect(() => {
    const container =
      containerRef.current;

    if (
      !container ||
      mapRef.current
    ) {
      return;
    }

    /* -------------------------------------------------------
       BASEMAP CHECK
    ------------------------------------------------------- */

    const cartoKey =
      getCartoKey();

    if (!cartoKey) {
      setBasemapUnavailable(false);
    }

    /* -------------------------------------------------------
       CREATE MAP
    ------------------------------------------------------- */

    const map =
      new maplibregl.Map({
        container,

        style: resolveInitialStyle(),

        center: [
          77.59435,
          12.9713,
        ],

        zoom: 17,

        pitch: 0,

        bearing: 0,

        attributionControl: {
          compact: true,
        },
      });

    mapRef.current = map;

    /* =====================================================
       NAVIGATION CONTROL
    ===================================================== */

    map.addControl(
      new maplibregl.NavigationControl({
        showCompass: true,
        visualizePitch: true,
      }),
      "top-right"
    );

    /* =====================================================
       RESIZE OBSERVER
    ===================================================== */

    const resizeObserver =
      new ResizeObserver(() => {
        map.resize();
      });

    resizeObserver.observe(
      container
    );

    /* =====================================================
       STYLE LOAD
    ===================================================== */

    map.on("style.load", () => {
      addUnitsSourceAndLayers(
        map,
        unitsRef.current,
        filterRef.current,
        showUndergroundRef.current,
        viewModeRef.current
      );

      /* ---------------------------------------------------
         INITIAL SELECTION
      --------------------------------------------------- */

      if (
        selectedUlpinRef.current
      ) {
        applySelection(
          map,
          selectedUlpinRef.current,
          unitsRef.current,
          didClickRef
        );
      }

      /* ---------------------------------------------------
         EXACT GEOJSON POSITION
      --------------------------------------------------- */

      const bounds =
        computeBounds(
          unitsRef.current
        );

      if (bounds) {
        map.fitBounds(
          bounds,
          {
            padding: 90,
            duration: 0,
            maxZoom: 18,
          }
        );
      }

      mapReadyRef.current =
        true;

      console.log(
        "Map2D: MapLibre ready"
      );

      console.log(
        "Map2D: rendered features:",
        unitsRef.current.length
      );

      console.log(
        "Map2D: GeoJSON bounds:",
        bounds
      );
    });

    /* =====================================================
       MAP ERRORS
    ===================================================== */

    map.on("error", (event) => {
      const sourceId =
        (
          event as {
            sourceId?: string;
          }
        ).sourceId;

      if (
        sourceId === SOURCE_ID
      ) {
        return;
      }

      if (
        sourceId ===
          BASEMAP_RASTER_SOURCE_ID &&
        !blueprintAppliedRef.current
      ) {
        blueprintAppliedRef.current =
          true;

        setBasemapUnavailable(
          true
        );

        map.setStyle(
          createBlueprintStyle()
        );
      }
    });

    /* =====================================================
       HOVER
    ===================================================== */

    map.on(
      "mousemove",
      (event) => {
        if (
          !mapReadyRef.current
        ) {
          return;
        }

        const layerIds = [
          FILL_LAYER_ID,
          EXTRUDE_LAYER_ID,
        ].filter((id) =>
          Boolean(
            map.getLayer(id)
          )
        );

        if (
          layerIds.length === 0
        ) {
          return;
        }

        const features =
          map.queryRenderedFeatures(
            event.point,
            {
              layers: layerIds,
            }
          );

        const feature =
          features[0];

        const id =
          feature?.properties?.ulpin ??
          feature?.id;

        setHoverState(
          map,
          hoveredIdRef,
          id == null
            ? null
            : String(id)
        );
      }
    );

    /* =====================================================
       CLICK
    ===================================================== */

    map.on(
      "click",
      (event) => {
        if (
          !mapReadyRef.current
        ) {
          return;
        }

        const layerIds = [
          FILL_LAYER_ID,
          EXTRUDE_LAYER_ID,
        ].filter((id) =>
          Boolean(
            map.getLayer(id)
          )
        );

        const features =
          map.queryRenderedFeatures(
            event.point,
            {
              layers: layerIds,
            }
          );

        /* -------------------------------------------------
           Click empty map
        ------------------------------------------------- */

        if (
          features.length === 0
        ) {
          didClickRef.current =
            null;

          onSelectRef.current(
            null
          );

          return;
        }

        /* -------------------------------------------------
           Prefer actual building/floor/unit
           instead of parcel when stacked.
        ------------------------------------------------- */

        const target =
          features.find(
            (feature) =>
              feature.properties
                ?.unit_type !==
              "parcel"
          ) ??
          features[0];

        const ulpin =
          target.properties?.ulpin ??
          target.id;

        if (
          ulpin == null
        ) {
          return;
        }

        const selectedId =
          String(ulpin);

        didClickRef.current =
          selectedId;

        onSelectRef.current(
          selectedId
        );
      }
    );

    /* =====================================================
       CLEANUP
    ===================================================== */

    return () => {
      resizeObserver.disconnect();

      mapReadyRef.current =
        false;

      map.remove();

      mapRef.current =
        null;
    };
  }, []);

  /* =======================================================
     UPDATE GEOJSON
  ======================================================= */

  useEffect(() => {
    const map =
      mapRef.current;

    if (
      !map ||
      !mapReadyRef.current
    ) {
      return;
    }

    const source =
      map.getSource(
        SOURCE_ID
      ) as
        | maplibregl.GeoJSONSource
        | undefined;

    if (!source) {
      return;
    }

    source.setData({
      type: "FeatureCollection",
      features: units,
    });
  }, [units]);

  /* =======================================================
     UPDATE FILTER
  ======================================================= */

  useEffect(() => {
    const map =
      mapRef.current;

    if (
      !map ||
      !mapReadyRef.current
    ) {
      return;
    }

    applyFilter(
      map,
      filter,
      showUnderground
    );
  }, [
    filter,
    showUnderground,
  ]);

  /* =======================================================
     UPDATE SELECTION
  ======================================================= */

  useEffect(() => {
    const map =
      mapRef.current;

    if (
      !map ||
      !mapReadyRef.current
    ) {
      return;
    }

    applySelection(
      map,
      selectedUlpin,
      units,
      didClickRef
    );
  }, [
    selectedUlpin,
    units,
  ]);

  /* =======================================================
     UPDATE VIEW MODE
  ======================================================= */

  useEffect(() => {
    const map =
      mapRef.current;

    if (
      !map ||
      !mapReadyRef.current
    ) {
      return;
    }

    applyViewMode(
      map,
      viewMode
    );
  }, [viewMode]);

  /* =======================================================
     UI
  ======================================================= */

  return (
    <div
      className={`map2d-root ${
        className ?? ""
      }`}
    >
      {/* MAPLIBRE CANVAS */}

      <div
        ref={containerRef}
        className="map2d-canvas"
      />

      {/* BASEMAP WARNING */}

      {basemapUnavailable && (
        <div
          className="map2d-basemap-warn"
          role="status"
        >
          Real basemap unavailable —
          blueprint mode active
        </div>
      )}

      {/* MAP INFO */}

      <div className="map2d-info">
        <div className="map2d-info-title">
          2D · MAPLIBRE
        </div>

        <div>
          Bengaluru cadastral overlay
        </div>

        <div>
          {units.length} units · EPSG:4326
        </div>
      </div>

      {/* LEGEND */}

      <div
        className="map2d-legend"
        aria-label="Status legend"
      >
        <div className="legend-title">
          STATUS
        </div>

        {Object.entries(
          STATUS_COLORS
        ).map(
          ([status, color]) => (
            <div
              key={status}
              className="legend-item"
            >
              <span
                className="legend-dot"
                style={{
                  background: color,
                }}
              />

              {status}
            </div>
          )
        )}
      </div>

      {/* TOOLBAR */}

      <div className="map2d-toolbar">
        <button
          type="button"
          onClick={fitToData}
        >
          ⌖ Fit to data
        </button>
      </div>
    </div>
  );
};

export default Map2D;