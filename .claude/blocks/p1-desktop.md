# P1 · desktop application shell

**Owner:** P1 Desktop Team · **Path:** `desktop/`

## Scope

The desktop application shell providing 2D/3D land mapping interfaces, automated AI detection & analysis tools, 3D ownership unit creation, verification & review workflows, error checking, history log tracking, and export capabilities.

Built with **Tauri v2** + **React 19** + **Vite 7** as a cross-platform desktop wrapper around standard web mapping and 3D visualization components.

```
desktop/
├── src/
│   ├── components/       reusable UI elements & layout wrappers
│   ├── pages/            application screens (Dashboard, Map, Review, etc.)
│   ├── data/             sidecar client, shared document provider, UI config
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


---

## The demo build: no sign-in, no sample data, creation is the only way in

Three changes made on 2026-09-05, all in the same direction. Recorded here because each
one removed something a reader will otherwise go looking for.

**The login screen was removed.** `LoginPage.jsx` is deleted and `App.jsx` no longer
gates on `isLoggedIn`. The whole flow — upload, AI review, approval, export — runs as one
operator. The screen only ever set a role string on a mock user; who decided what is
recorded by the sidecar in `review.decided_by`, and always was. Multi-user access is
FR-11 and needs a real identity store, not a form with no password field. The *Sign Out*
button in the project header and the unused `onLogout` prop on `AppShell` went with it.

**All fabricated data was removed, and `data/mockData.js` deleted.** Seventeen exports,
consumed by eleven screens, each behind a `live && doc ? real : mock` fallback. The
fallback was the problem: an offline sidecar produced a dashboard of plausible numbers,
an audit trail of edits by people who do not exist, and four uploaded files carrying
validation results for checks that had never run. Screens now render empty and say why.

Two of the seventeen were not data and were kept, under honest names:

- `data/layers.js` (`MAP_LAYERS`) — which layers the map panel offers. UI configuration.
- `data/aiTools.js` (`AI_TOOLS`) — the catalogue of P3 operations. Its `lastRun` and
  `status` fields were dropped: a screen reporting a model "last ran at 10:20 AM" when
  nothing had ever run is the kind of detail nobody thinks to doubt.

**Project creation replaced project selection.** `ProjectSelectPage.jsx` listed three
invented projects with invented parcel counts, and "creating" one built a JavaScript
object that never reached disk. `CreateProjectPage.jsx` is a three-step wizard that
posts to `POST /cadastre/project` and produces a real GeoPackage. There is no list of
existing projects, because a project this application did not build is one whose numbers
came from nowhere.

### What the wizard collects, and why those fields

Not a design — `contracts/inbound/p2-geopackage.md`. Step one writes the single row of
`project_settings`; each source in step two writes one row of `source`.

Source types are fetched from `GET /cadastre/source-types` rather than hardcoded, so the
form and `project.py` cannot drift: a type the form offers but the backend does not
handle is a file the operator selects and the project silently ignores.

The nine types cover the problem statement's input list exactly — GIS parcel layers,
building footprints, utility lines, DEM, DSM, drone imagery, LiDAR/point cloud, floor
plans, GNSS/CORS control.

**Every source states its own accuracy, and the field cannot be skipped.** This is the
part that looks like bureaucracy and is not: P4 derives every geometric tolerance from
`horizontal_accuracy_m` and `vertical_accuracy_m`. The wizard pre-fills the *conservative*
end of each instrument's usual range and defaults `processing_status` to
`accuracy_estimated`, because under-claiming accuracy is safe and over-claiming is not —
a too-tight tolerance reports measurement noise as encroachment until reviewers learn to
dismiss warnings.

**Sources are named by path, not uploaded.** The sidecar runs on the same machine; that
is the whole desktop-first design. A 12 GB point cloud is read where it lies. File
selection uses `@tauri-apps/plugin-dialog`, added in the same change (npm package, the
`tauri-plugin-dialog` crate, registration in `src-tauri/src/lib.rs`, and `dialog:default`
in `capabilities/default.json`).

**`cadastreApi.js` no longer has a default project path.** It was `'pilot.gpkg'`, which
on a fresh install quietly served the demo fixture — a screen that looks right and
belongs to somebody else's data. It now starts empty and `setProjectPath()` is called
once, when the wizard returns.

### `.cargo/config.toml` held a Windows path

`desktop/src-tauri/.cargo/config.toml` set `target-dir = "C:/rust_target/sih1"`. On Linux
and macOS that is a *relative* path, so cargo resolved it under `src-tauri/` and then
failed joining `LD_LIBRARY_PATH`, where `:` is the separator. **The block could not build
natively off Windows.** The file is deleted; the default `target/` is already covered by
`src-tauri/.gitignore`. A machine-specific target directory belongs in that developer's
own `~/.cargo/config.toml` or `CARGO_TARGET_DIR`, never committed.

## Second honesty pass — controls that reported states they did not have

The first pass removed fabricated *data*. This one removes fabricated *state*: indicators,
counts and controls that described something the app was not doing.

**The shell's own status was hardcoded.** Two nav badges (`7` errors, `12` to review)
rendered whenever the sidecar was offline, beside the banner saying there was no data —
they now come from the document or do not render. The status bar's green pulsing
"Connected" pill read the same `status` every screen already uses, so the shell can no
longer contradict the page it frames; only `live` is green and pulsing. Its fixed
`Lat 12.9716° / Lon 77.5946° / Elev 920.45 m / Scale 1:2,500` — Bengaluru, shown over
every project — is replaced by the project's CRS and vertical datum. The clock no longer
forces `en-IN`, and the version string is `__APP_VERSION__`, defined in `vite.config.js`
from `package.json`, so a build cannot announce a version it is not.

**The 2D map opened over Bengaluru.** `center = [12.9720, 77.5950]`, `zoom 17`, whatever
the project held. It now opens on the project's own bounds, and a project with no geometry
gets an empty state rather than a map centred on a city it has nothing to do with — a
default centre is a claim about where the data is. The same fixed Lat/Lon/Elev/Scale
overlay is now a real cursor readout: position from Leaflet's `mousemove`, the live zoom,
and **metres per pixel rather than a scale ratio** — a `1:2,500` needs the display's
physical size, which a browser does not know. There is no elevation because only the
sidecar reads the DEM. Reports are throttled to ten a second; `mousemove` fires per pixel
and each one re-renders a page holding every polygon in the project.

**The layer panel was decoration.** Eleven checkboxes and eleven opacity pills over a
`toggleLayer` nothing read, above a map that drew its tiles, parcels and buildings
unconditionally — plus a search box with no handler. Eight of the eleven named things this
app cannot render at all (satellite imagery, roads, DEM, DSM, survey and control points).
`data/layers.js` now lists only what one of the two views genuinely draws, each entry
declaring the `views` it applies to and the contract `unitType` it renders; the panel
disables a row and says why when the project holds no such units or the current view does
not draw them. Toggles and opacity are applied at the point of drawing, in both Leaflet
and the Three.js scene, and the search box filters. Rasters are deliberately absent: a
project registers them and `derive` reads them off disk, but nothing here renders one.

**Project Settings was entirely local state.** A Save button that flashed a green tick and
wrote nothing; a CRS read from `project.crs` when the sidecar sends `project_crs`, so it
always fell back to EPSG:4326 and contradicted the sidebar; a ULPIN prefix invented for one
demo ward (`29-BLR-042`) and an example identifier to match; a tile server and an
`ai.ulpin.gov.in` endpoint no code reads. The page now renders `doc.project` **read-only**
and says why: these were written once at creation, every unit already carries them, and
changing one would invalidate every identifier and tolerance already issued. The identifier
format shown is the real one from `ulpin/encode.py`, as a shape with named placeholders
rather than a fabricated example ULPIN.

**Create 3D Unit wrote nothing and said otherwise.** A four-step wizard with no API import
that prefilled a building and parcel from the demo ward, multiplied a height difference by
a magic `55.73` for a "Calculated Volume", drew a fixed SVG box as a preview of the
operator's geometry, and ended on an invented ULPIN with a Draft badge and "This unit
requires review and approval before it becomes an official record" — for a record that did
not exist. There is no sidecar route for manual creation, and the missing piece is
geometry: a unit is a prism over a real outline and this app cannot draw one. The route and
nav entry stay; the body is an honest not-built state pointing at Upload Data and AI Tools,
which do mint units.

**One source-accuracy table, in `data/sourceKinds.js`.** The wizard and the Upload Data
screen each held their own, and they disagreed — a footprint layer was 0.30/0.50 m through
one and 2.00/5.00 m through the other, DEM 0.50/0.30 against 0.20/0.10. Every validation
tolerance is `k * sqrt(acc_a² + acc_b²)` over those numbers, so the same file produced
different findings depending on which screen the operator opened. Where they disagreed the
looser number won, per the standing rule that under-claiming accuracy is safe. Upload also
offered `control`, which is not a `source_type` the sidecar knows — `survey_control` is —
so that card's files would have been refused with a 422.

**Search never rendered an approved unit as approved.** It compared `status === 'Approved'`
against the lowercase values the contract emits.

**Dead code removed:** `DashboardPage`'s `ProgressRing`, `DonutChart`, `statusData`,
`statusClass` and its own `iconMap`; `MapPage`'s `generateParcelPolygon`,
`generateBuildingPolygon` and the unused `selectedBuildingData`. The dashboard's "Active
Processing Jobs" and "Recent Activity" tables rendered five column headers over
permanently empty arrays, which reads as "nothing is running" rather than "nothing is
asking" — both now carry the same `NothingYet` explanation the rest of the app uses.
There is no job queue (ingest, derive, detect and validate are synchronous calls from
their own screens) and no audit log; what each decision recorded lives on the thing
decided.
