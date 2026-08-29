/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CARTO_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '*.geojson' {
  const data: import('./types/viewer').UnitFeatureCollection;
  export default data;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const Cesium: any;
