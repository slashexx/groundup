import type { StyleSpecification } from 'maplibre-gl';

export const BASEMAP_RASTER_SOURCE_ID = 'bengaluru-basemap';
export const BASEMAP_RASTER_LAYER_ID = 'bengaluru-basemap-layer';

const OSM_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const CARTO_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, © <a href="https://carto.com/attributions">CARTO</a>';

export function getCartoKey(): string {
  return (import.meta.env.VITE_CARTO_KEY ?? '').trim();
}

function createCartoTileUrls(key: string): string[] {
  const query = `key=${encodeURIComponent(key)}`;

  return ['a', 'b', 'c', 'd'].map(
    (subdomain) =>
      `https://${subdomain}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?${query}`,
  );
}

function createOSMTileUrls(): string[] {
  return [
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  ];
}

export function createOSMBasemapStyle(): StyleSpecification {
  return {
    version: 8,
    name: 'openstreetmap',
    sources: {
      [BASEMAP_RASTER_SOURCE_ID]: {
        type: 'raster',
        tiles: createOSMTileUrls(),
        tileSize: 256,
        attribution: OSM_ATTRIBUTION,
        maxzoom: 19,
      },
    },
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: {
          'background-color': '#e8eef2',
        },
      },
      {
        id: BASEMAP_RASTER_LAYER_ID,
        type: 'raster',
        source: BASEMAP_RASTER_SOURCE_ID,
        paint: {
          'raster-opacity': 1,
        },
      },
    ],
  };
}

export function createCartoBasemapStyle(
  key: string,
): StyleSpecification {
  return {
    version: 8,
    name: 'carto-voyager',
    sources: {
      [BASEMAP_RASTER_SOURCE_ID]: {
        type: 'raster',
        tiles: createCartoTileUrls(key),
        tileSize: 256,
        attribution: CARTO_ATTRIBUTION,
        maxzoom: 20,
      },
    },
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: {
          'background-color': '#e8eef2',
        },
      },
      {
        id: BASEMAP_RASTER_LAYER_ID,
        type: 'raster',
        source: BASEMAP_RASTER_SOURCE_ID,
        paint: {
          'raster-opacity': 1,
        },
      },
    ],
  };
}

export function createBlueprintStyle(): StyleSpecification {
  return {
    version: 8,
    name: 'cadastral-blueprint',
    sources: {},
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: {
          'background-color': '#e8eef2',
        },
      },
    ],
  };
}

export function resolveInitialStyle(): StyleSpecification {
  const key = getCartoKey();

  if (key) {
    return createCartoBasemapStyle(key);
  }

  return createOSMBasemapStyle();
}