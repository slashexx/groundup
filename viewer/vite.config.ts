import react from '@vitejs/plugin-react'
import cesiumUntyped from 'vite-plugin-cesium'
import { defineConfig, type Plugin } from 'vite'

// vite-plugin-cesium ships CJS-flavored types that misresolve under nodenext;
// at runtime Vite loads its ESM build where the default export IS the factory.
const cesium = cesiumUntyped as unknown as (options?: { rebuildCesium?: boolean }) => Plugin

// cesium() copies Cesium's static assets (workers, WASM, widget CSS) into the
// bundle and sets CESIUM_BASE_URL — required for fully offline operation.
export default defineConfig({
  plugins: [react(), cesium()],
})
