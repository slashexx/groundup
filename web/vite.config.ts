import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import cesiumUntyped from 'vite-plugin-cesium'
import { defineConfig, type Plugin } from 'vite'

// vite-plugin-cesium ships CJS-flavored types that misresolve under nodenext;
// at runtime Vite loads its ESM build where the default export IS the factory.
const cesium = cesiumUntyped as unknown as (options?: { rebuildCesium?: boolean }) => Plugin

const viewerLib = fileURLToPath(new URL('../viewer/src/lib', import.meta.url))

// The web app forks nothing: all components come from P5's library via @viewer.
// cesium() bundles Cesium's static assets so the published site is self-contained.
export default defineConfig({
  plugins: [react(), cesium()],
  resolve: {
    alias: { '@viewer': viewerLib },
    // The aliased lib sits under viewer/, whose bare imports would otherwise
    // resolve to viewer/node_modules — two React copies break hooks, two
    // Cesium copies break `picked.id instanceof Cesium.Entity`.
    dedupe: ['react', 'react-dom', 'cesium', 'maplibre-gl', 'proj4'],
  },
  server: { fs: { allow: ['..'] } },
})
