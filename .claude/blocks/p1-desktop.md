# P1 · desktop application shell

**Owner:** P1 Desktop Team · **Path:** `desktop/`

## Scope

The desktop application shell providing user authentication, 2D/3D land mapping interfaces, automated AI detection & analysis tools, 3D ownership unit creation, verification & review workflows, error checking, history log tracking, and export capabilities.

Built with **Tauri v2** + **React 19** + **Vite 7** as a cross-platform desktop wrapper around standard web mapping and 3D visualization components.

```
desktop/
├── src/
│   ├── components/       reusable UI elements & layout wrappers
│   ├── pages/            application screens (Dashboard, Map, Review, etc.)
│   ├── data/             local mock/seed state for UI prototyping
│   ├── index.css         global design system & component styles
│   └── App.jsx           react router navigation & view dispatcher
├── src-tauri/            Rust desktop shell configuration & native capabilities
├── public/               static visual assets & icons
└── package.json          npm script entry points & dependencies
```

```bash
cd desktop && npm install && npm run dev     # launch Vite dev server
cd desktop && npm run tauri dev              # launch full Tauri desktop application window
```

## Interface with P4 & P5 (agreed at the contract surface)

- **P5 Viewer integration:** Embeds 2D and 3D map views (via Leaflet / Three.js / MapLibre / Cesium layers) to display cadastre parcels, building footprints, and 3D vertical units.
- **P4 Cadastre API integration:** Consumes P4 FastAPI backend endpoints (`/api/v1/units`, `/api/v1/lifecycle`, `/api/v1/health`) for ULPIN queries, validation findings, and approval lifecycle management.

## Decisions

- **Tauri v2 + React 19 Stack:** Selected for native lightweight execution, low memory overhead, and secure OS-level file system access without Electron bundle bloat.
- **Client-side Routing (`react-router-dom` v7):** Enables smooth multi-screen navigation (Dashboard, Map, Create Unit, Error Check, AI Tools, Review, Export, Settings) within a single desktop application context.
- **Modular Pages Architecture:** Isolates specific reviewer workflows into focused page components under `src/pages/`.
- **Strict `.gitignore` enforcement:** Ignores build artifacts (`dist`, `dist-ssr`, `.vercel`), Rust compilation binaries (`src-tauri/target`), auto-generated schemas (`src-tauri/gen`), and `node_modules` from repository tracking.

## Observed state (2026-08-31)

Desktop shell frontend fully implemented with complete UI routes (`DashboardPage`, `MapPage`, `Create3DUnitPage`, `ReviewPage`, `AIToolsPage`, `ExportPage`, `ErrorCheckPage`, `HistoryPage`, `SettingsPage`, `SearchPage`, `ProjectSelectPage`, `LoginPage`). Ready for integration with P4 backend endpoints and P5 viewer components.
