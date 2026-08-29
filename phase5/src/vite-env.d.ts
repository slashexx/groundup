/// <reference types="vite/client" />

declare module '*.geojson' {
  const data: import('./types/viewer').UnitFeatureCollection;
  export default data;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const Cesium: any;
