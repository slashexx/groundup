# P6 · web app, publish & demo

**Owner:** rudraksha · **Path:** `web/`

## Scope

The read-only published viewer and the pipeline that produces it: export the project
document, stamp a manifest, build a static site, deploy. Hands off: the live shareable
link. Pitch deck and demo script are also P6 scope but live outside the repo for now.

```
web/
├── src/App.tsx          read-only app: provenance strip + P5 components
├── tools/publish.mjs    obtain document → refuse or stamp a manifest → build → deploy
├── tools/bundle.mjs     the pure decisions: what is refused, and what "checked" means
├── tools/bundle.test.mjs
└── public/data/         document.json + manifest.json — the published bundle
                         (committed output, like the fixture: consumable without running our code)
```

```bash
cd web && pnpm install                # viewer/ must also be installed (see note below)
pnpm dev                              # local dev against the committed bundle
pnpm test                             # what the publish pipeline refuses (node:test, no deps)
pnpm publish:fixture[:deploy]         # bundle = contracts/fixtures/demo-parcel.json
pnpm publish:live[:deploy] [--db P]   # bundle = GET /cadastre/document from a running sidecar
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
  P6-specific format exists, deliberately: fixture and live export are interchangeable.
- **`publish:live` also reads `GET /cadastre/runs/latest`**, for the run id and ruleset
  version that go in the manifest. Its absence is not what gates a publish — see the
  unvalidated-record refusal below — it only names the run that cleared the record.

## The chain, end to end (2026-09-04)

`publish:live` needs a project that has been ingested, derived *and* validated, in that
order. Five commands, and getting the order wrong used to fail quietly: publish after
ingest but before derive and the site renders flat plates; publish before validation and
it renders "0 findings", which reads as *checked and clean* rather than *never checked*.
So the sidecar side is now one command that says what each step did:

```bash
./.venv/bin/python sidecar/cadastre/tools/run_chain.py --gpkg pilot.gpkg
./.venv/bin/python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000
cd web && pnpm publish:live --db pilot.gpkg          # add --deploy to push to Netlify
```

`run_chain.py` runs P2's pipeline over its sample data, imports the layers, registers
synthetic elevation, derives heights and floors, and validates. `--no-rasters` skips the
elevation step, which is how you see the FR-03 path: heights stay absent,
HEIGHTS_UNAVAILABLE is raised, and the record says so rather than guessing.

Three P4-side defects were only visible once P6 published live data, and all three are
fixed in `sidecar/cadastre/` rather than worked around here:

- **Every published building had no parcel above it.** `ingest_gpkg` wrote the parcel →
  building `contains` edge but not the reciprocal `inside`, and `viewer/src/lib/adapter.ts`
  builds `parent_id` from `inside` *alone*. The extract panel's lineage therefore opened
  at the building — the wrong way round for a land record. The fixture and `derive` had
  always stored both directions; ingest was the outlier.
- **Derived floors published as raw uuid4s.** `04-ulpin.md` says a unit in `needs_review`
  carries a provisional identifier; floors created by `derive` were the one kind that
  carried none, so the units that *are* the vertical subdivision showed no identifier at
  all. `derive._identify` now mints one per floor (`A00-001`, `A01-000`, …), refusing
  when the building has no parent parcel rather than minting under a placeholder.
- **A mistyped `--db` answered 500 with a stack trace.** `store.load_project` guarded its
  reads of P2's `source` and `project_settings` tables but not of our own `unit` and
  `unit_relationship`, so a GeoPackage `init_schema` had never touched raised a bare
  `sqlite3.OperationalError`. It matters here because `sqlite3.connect` *creates* an
  empty file for a path that does not exist: a typo in `--db` arrives at the endpoint as
  a blank database, not as an error. Now 422 with a message naming the path and the
  ingest call. The existing empty-project test missed it by calling `init_schema` first.

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
- **Every instrument reads the same datum** (brilliance pass, same day): the cut is drawn
  *in the scene* as a red section-trace rectangle at the slice elevation (P5's Viewer3D
  owns it; entity ids prefixed `__` are scene furniture and never selectable); the gauge
  carries a **strata registry** — every volume's real vertical span as a hairline-articulated
  bar in its validation color, with the selected unit's span in amber; the plan sheet has
  survey registration marks and a north arrow; panels settle in a 320 ms staggered load
  sequence (reduced-motion respected).
- **Search selects, it does not cull**: the query drives Enter-to-select and is stripped
  from the filter passed to the viewers, so spatial context never disappears. Type and
  validation chips still filter the scene.

- **An unvalidated record is not publishable** (2026-09-04, integration): `publish:live`
  refuses a document containing any unit whose `validation_state` is `unvalidated`. The
  reason is that `findings: []` renders identically whether the record was checked and
  came back clean or was never checked at all, and on a published page those read as the
  same reassuring zero — the same failure class as the approval guard in `04-ulpin.md`,
  where missing information was treated as *nothing to check*. `validation_state` is the
  honest signal because `store.save_run` writes it back only for the units its run
  actually covered, so this catches both the project nobody validated and the one
  validated before `derive` added its floors. The error names the curl that fixes it.
  *Failed units do not block a publish* — a record with errors is exactly what the
  viewer is for; a record nobody looked at is not.
  **The fixture is exempt**: 14 of its 16 units are deliberately `unvalidated`, because
  there they are authored content and not the residue of a run. Applying the live rule to
  it would have broken `publish:fixture`, the demo path, and a test asserts it does not.
- **The manifest says what produced its findings**: `validation` is
  `{kind: "run", run_id, ruleset_version}` live and `{kind: "fixture-expectations"}` for
  the fixture, and the strip renders `checked · run ba182e23 · ruleset r1`. When the run
  endpoint cannot be reached the strip says *provenance unavailable* rather than
  *checked* — a check we cannot name is not a check we should claim.
- **The manifest carries the bundle's file name, never its path.** It read
  `live · /home/…/scratch/pilot.gpkg` on the first live publish; the manifest is served
  on a public URL, so that published the operator's directory layout to anyone who opened
  the link. `basename()` at the point of capture, not at the point of display.
- **The provenance strip has a lane, and the extract owns the rest.** It is one line at
  `top: 66px` and `.record` floats over its right end from `top: 76px`, so an unbounded
  line slid under the panel and the tail was simply lost — the first live publish's
  absolute path was how we noticed. `right: 444px` reserves the lane whether or not an
  extract is open (a strip that resized on selection would be worse), and what still does
  not fit is ellipsised with the whole line on `title`.
- **The publish pipeline's decisions are testable**: `tools/bundle.mjs` holds the two pure
  ones (`refusalFor`, `validationOf`), `tools/publish.mjs` stays the script that fetches,
  writes and builds. `pnpm test` runs `node:test` against them — no framework, because a
  guard that only holds when a dependency is installed is not much of a guard.

## Observed state (2026-09-04)

**The full chain has been run end to end and published.** `run_chain.py` over P2's sample
data produces 7 units (1 parcel, 1 building, 5 floors), every one with a provisional
ULPIN, validating clean under ruleset `r1`; `publish:live` bundles it and the site renders
the stack with the lineage reading `parcel › building › floor`. Verified headless on Linux
(`CHROME_PATH=/usr/bin/chromium`; the skill's Chrome path is macOS-only) — zero console
errors, zero non-same-origin requests.

The committed bundle in `public/data/` is the **fixture** publish, not that live one: it
is richer (16 units, 5 planted findings, apartments and an underground feature) and it is
reproducible from the repo, whereas the live bundle depends on a GeoPackage that is not
committed. `publish:fixture` re-emits the identical `document.json`, so the committed
artefact is verifiably output rather than hand-edited.

Fixture bundle re-verified headless after the integration changes: provenance strip within
its lane, search → APT-102 → planted OVERLAP_SIBLING finding with `parcel › building ›
floor › apartment` lineage, section cut at 6.0 m drawn in the scene, underground toggle,
missing-bundle gate showing "No published record" rather than falling back. All pass.

The three publish failure paths were exercised against a running sidecar after the fix:
`--db` at a non-project → 422 naming the path and the ingest call; `--db` at an
ingested-but-unvalidated project → refusal naming the validate curl, with the committed
bundle byte-identical afterwards; the complete project → 7 units published.

Not yet: CI (neither `pnpm test` nor a deploy runs on push — `cadastre.yml` is scoped to
`sidecar/cadastre/**` and `contracts/**`, and its own comment says other blocks add their
own workflows, so this is P6's to add); 3D-tiles in the bundle; pitch deck. The live
publish has not been `--deploy`ed to Netlify — the committed fixture bundle is what the
public link currently serves, and pushing the synthetic 7-unit project over it is a call
for the block's owner.
