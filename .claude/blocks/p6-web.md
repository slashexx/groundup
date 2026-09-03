# P6 · web app, publish & demo

**Owner:** rudraksha · **Path:** `web/`

## Scope

The read-only published viewer and the pipeline that produces it: export the project
document, stamp a manifest, build a static site, deploy. Hands off: the live shareable
link. Pitch deck and demo script are also P6 scope but live outside the repo for now.

```
web/
├── src/App.tsx          read-only app: provenance strip + P5 components
├── tools/publish.mjs    obtain document → validate → manifest → build → deploy
└── public/data/         document.json + manifest.json — the published bundle
                         (committed output, like the fixture: consumable without running our code)
```

```bash
cd web && pnpm install                # viewer/ must also be installed (see note below)
pnpm dev                              # local dev against the committed bundle
pnpm publish:fixture[:deploy]         # bundle = contracts/fixtures/demo-parcel.json
pnpm publish:live[:deploy]            # bundle = GET /cadastre/document from a running sidecar
```

Live link: **https://sih26011-3d-ulpin.netlify.app** (Netlify site id
`98f77c41-0f57-4936-bda4-e0416d709a2f`, baked into `tools/publish.mjs`; manual CLI
deploys, not yet CI).

## Interfaces

- **Consumes P5's library, forks nothing.** `@viewer` aliases `../viewer/src/lib` in
  `web/vite.config.ts`. Because the aliased sources resolve bare imports against
  `viewer/node_modules`, both `viewer/` and `web/` need `pnpm install`, dependency
  versions must match viewer's (including the maplibre-gl v5 pin), and
  `resolve.dedupe` covers react/cesium/maplibre/proj4 — two React copies break hooks,
  two Cesium copies break `instanceof Cesium.Entity` picking. Caught live: the first
  build crashed with `Cannot read properties of null (reading 'useState')` until dedupe
  was added.
- **The publish bundle IS the P4 export document** (`GET /cadastre/document`) — the same
  shape as `contracts/fixtures/demo-parcel.json`, per `.claude/06-contracts.md`. No
  P6-specific format exists, deliberately: fixture and live export are interchangeable,
  and P6 works from `main` today while `publish:live` starts working the moment the
  integration branch merges (the endpoint currently exists only on
  `integrate-p1-p2-p4-p5`).

## Decisions

- **Runtime fetch, not build-time import** (unlike the viewer demo): the bundle is data,
  swappable by republishing without rebuilding, and the app states its provenance — the
  strip shows exported-at, unit/finding counts and source from `manifest.json`.
- **A broken publish fails loudly at both ends.** `publish.mjs` refuses a document with
  no `units[]`/`project` (exit 1, nothing written); the app renders an explicit
  "No published record" state instead of falling back to bundled data — a judge must
  never mistake a stale fallback for the published record. Static hosts answer missing
  files with the SPA's index.html (HTTP 200), so the app validates JSON, not status.
- **Same offline discipline as P5**: system font stacks, no external requests;
  verification captures the network and fails on any non-same-origin request.
- Reuses the existing Netlify site rather than minting a second link — one shareable URL
  for the team, history preserved.

- **UI is a drafting sheet over one full-bleed scene** (2026-09-03 revamp): the 3D scene
  is the page; chrome floats as paper panels — plan inset (bottom-left, expandable),
  record extract (right, only when a unit is selected), mono provenance line. The
  signature control is the **elevation gauge**: a graduated metre ruler (ground line ±0,
  hatched below-grade zone, floor ticks derived from the data) whose draggable red handle
  IS the section cut; red is reserved for the cut. System font stacks only — the
  offline/zero-request rule outweighed the font pairing a design pass suggested.
- **Search selects, it does not cull**: the query drives Enter-to-select and is stripped
  from the filter passed to the viewers, so spatial context never disappears. Type and
  validation chips still filter the scene.

## Observed state (2026-09-03)

Fixture bundle published and verified headless (banner, search → APT-102 planted
OVERLAP_SIBLING finding, slice, underground; missing-bundle gate; publish refusal on
unreachable sidecar — all pass, zero external requests, zero console errors). Not yet:
CI deploys, `publish:live` exercised against a real sidecar (endpoint unmerged),
3D-tiles in the bundle, pitch deck.
