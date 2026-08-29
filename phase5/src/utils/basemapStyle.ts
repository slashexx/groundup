import type { StyleSpecification } from 'maplibre-gl';

export const BASEMAP_RASTER_SOURCE_ID = 'bengaluru-basemap';
export const BASEMAP_RASTER_LAYER_ID = 'bengaluru-basemap-layer';

const CARTO_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, © <a href="https://carto.com/attributions">CARTO</a>';

export function getCartoKey(): string {
  return (import.meta.env.VITE_CARTO_KEY ?? '').trim();
}

function createCartoTileUrls(key: string): string[] {
  const query = `key=${encodeURIComponent(key)}`;
  return ['a', 'b', 'c', 'd'].map(
    (subdomain) =>
      `https://${subdomain}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?${query}`
  );
}

/** Fallback when the CARTO key is missing or tiles fail — parcels still render. */
export function createBlueprintStyle(): StyleSpecification {
  return {
    version: 8,
    name: 'cadastral-blueprint',
    sources: {},
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: { 'background-color': '#e8eef2' },
      },
    ],
  };
}

export function createCartoBasemapStyle(key: string): StyleSpecification {
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
        paint: { 'background-color': '#e8eef2' },
      },
      {
        id: BASEMAP_RASTER_LAYER_ID,
        type: 'raster',
        source: BASEMAP_RASTER_SOURCE_ID,
        paint: { 'raster-opacity': 1 },
      },
    ],
  };
}

export function resolveInitialStyle(): StyleSpecification {
  const key = getCartoKey();
  if (!key) {
    return createBlueprintStyle();
  }
  return createCartoBasemapStyle(key);
}
