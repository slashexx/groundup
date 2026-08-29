import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'geojson',
      transform(code, id) {
        if (id.endsWith('.geojson')) {
          return {
            code: `export default ${code}`,
            map: null,
          }
        }
      },
    },
  ],
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
