# P5 · viewer components

**Owner:** rudraksha (with pragati) · **Path:** `viewer/`

## Scope

The viewer component library consumed by P1 (desktop review screens) and P6 (static web
build): a MapLibre 2D map, a Cesium 3D viewer with floor slice and underground view,
search/filter, and a click-to-inspect details panel. One library, two hosts — the public
props (`viewer/src/lib/types.ts`) expose no MapLibre or Cesium types, data flows in as
plain objects and events come out as `onSelect(unit_id)`.

```
viewer/
├── src/lib/        the deliverable: Map2D · Viewer3D · SearchFilter · DetailsPanel
│   ├── types.ts    display model + component props (P5-owned contract)
│   └── adapter.ts  P4 outbound contract -> display model
└── src/demo/       dev harness (`pnpm dev`), renders the committed fixture
```

```bash
cd viewer && pnpm install && pnpm dev     # or: pnpm build && pnpm preview
```

## Interface with P4 (agreed at the contract surface)

The viewer consumes `contracts/outbound/unit.schema.json`, `finding.schema.json` and the
relationships array as committed in `contracts/fixtures/demo-parcel.json`. The demo
imports the fixture at build time, so regenerating the fixture updates the demo on the
next build with no coordination needed.

`adapter.ts` is the single place P4's shapes are translated for display:

- **Reprojection** — `footprint_2d` arrives in the project CRS (metres, per the schema's
  deliberate RFC 7946 deviation); converted once at load to WGS84 via proj4. UTM 326xx/327xx
  supported; anything else fails loudly rather than rendering in the wrong place.
- **Display ground** — engines put the globe surface at 0, so heights are shifted for
  display: ground = parcel `lower_limit` − `project.stratum_below_limit_m` (fallbacks:
  median `ground_level_m`, then min `lower_limit`). Raw datum values are preserved and the
  panel shows them verbatim (e.g. "918.5 m → 921.5 m EGM2008").
- **Unknown heights stay unknown** (FR-03) — rendered as a flat 1 m marker slab in a
  distinct grey, panel says "unknown — recorded as absent, never guessed". Never extruded
  from a guess.
- **Hierarchy** — breadcrumbs/children derive from `relationships` `rel_type: "inside"`.
- **Label** — `ulpin ?? ulpin_provisional ?? unit_id`; the panel marks provisional units
  ("assigned at approval").

## Decisions

- **Color encodes `validation_state`** (unvalidated/passed/warnings/failed), not `status` —
  check results are what a reviewer needs at a glance; status appears as a panel badge.
  Type overrides: parcels neutral slab, underground features grey.
- **Parcels render as a thin ground slab**, not their full legal stratum (−30 m…+150 m
  would be a 180 m box drowning the buildings); the stratum column is panel data.
- **Floor slice = entity filtering** (hide volumes whose base ≥ slice height). True
  clipping planes only apply to tilesets/models, not entity polygons — revisit if/when a
  photoreal mesh tileset exists.
- **Underground view** = Cesium globe translucency + camera collision off. Below-grade
  units render at their real negative display heights.
- **Filter semantics:** `undefined` = no restriction, empty array = matches nothing
  (caught as a bug when all-chips-off rendered everything).
- **maplibre-gl is pinned to v5.** v6 splits its web worker into a sibling module that
  404s under Vite prebundling and build — the style then never fires `load` and the map
  is silently blank with no console error. Do not upgrade without solving worker bundling.
- Fully offline by construction: no Cesium Ion, no external tiles/glyphs/fonts;
  `vite-plugin-cesium` bundles Cesium's static assets.

## Observed state (2026-08-29, updated 2026-09-03)

Components render the committed fixture end-to-end (search → cross-view highlight →
panel with findings; slice; underground) — verified headless, zero external requests,
zero console errors. Demo deploy: https://sih26011-3d-ulpin.netlify.app (manual CLI
deploy, not yet CI). Not yet done: embedding in P1's shell, 3D Tiles ingestion,
`affected_geometry` finding overlays on the map.

Since 2026-09-03 the library is also consumed by P6 (`web/` imports it via a Vite alias — see `.claude/blocks/p6-web.md` for the dedupe constraint that consumers must carry).

Correction (2026-09-03): `Map2D` selection `fitBounds` used a fixed 120 px padding; on small embedded maps (P6's plan inset) padding exceeding the canvas makes MapLibre zoom out to nothing. Padding is now clamped to a quarter of the smaller canvas dimension. Search placeholder shortened to fit narrow hosts.
