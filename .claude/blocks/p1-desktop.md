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

## Observed state (2026-09-02)

Thirteen routes implemented (the twelve above plus `UploadDataPage`).

**Four screens are wired to the P4 sidecar** — Dashboard, Review Records, Check Errors and
Search ULPIN — via `src/data/cadastreApi.js` and the `useCadastreDocument()` hook in
`src/data/useCadastre.jsx`. The remaining nine still render `src/data/mockData.js`.

Wiring decisions, agreed at the interface:

- **The mock is a fallback, and it announces itself.** When the sidecar is unreachable
  every wired screen shows `DataSourceBanner` saying so and naming the command that starts
  it. A reviewer looking at invented numbers believing they are the project is the failure
  this is built to prevent, so the fallback is never silent.
- **The guard is the feature.** Approve calls `POST /cadastre/units/{id}/transition` and
  shows the refusal verbatim when the validation guard rejects it, rather than reflecting
  success in the UI. The queue also pre-computes `approvable` with the same rule the
  server enforces, so the button state and the answer agree.
- **`Ack` appears only on warnings.** Errors are not acknowledgeable — the API answers 409
  — so offering the button on one would be offering an action that cannot succeed.
- **Confidence is absent, not zero.** A unit with no `confidence_score` shows "not
  AI-derived" instead of an empty bar, which reads as zero confidence.
- **`useCadastre.jsx`, not `.js`.** This package's Vite config only transforms `.jsx`; a
  component in a `.js` file fails the build with "Expression expected".

Not yet done: embedding P5's viewer components (`MapPage` still uses Leaflet/Three.js
directly), and the nine unwired screens.
