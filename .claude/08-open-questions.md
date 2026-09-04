# Open questions

Live list. Resolve items here and move the outcome into the relevant context file.

## Blocking nothing yet, but decide before Phase 2 ends

| Question | Notes |
|---|---|
| **Official ULPIN format** | Our scheme extends the 14-char parent and carries a version field precisely so this can change. Verify the internal field layout against DoLR's published ULPIN guidelines. |
| **Pilot city and dataset** — *no longer blocking* | Suggested: a Bengaluru or Pune ward with dense apartment stock **and an operating metro line**, which gives a genuine sub-surface case. Build the pipeline on open foreign LiDAR (AHN, Dublin ALS) because it is clean and classified; demo the registry on the Indian site. **Extrusion is already testable without this**: `tools/make_rasters.py` generates synthetic DEM/DSM with planted ground truth, which is strictly better for testing the algorithm than real data would be. Real data changes only the inputs. |
| **Accuracy targets** | Do not set a single number. Set a per-source error budget and propagate it into `confidence_score`. Refusing to state one figure is the honest answer and PRD §4.2 already commits us to it. |
| **Vertical datum and elevation source** | Orthometric via a published geoid model, with a **measured** per-building local offset (tie the plan's 0.000 to a surveyed point). Never assumed. P2 owns this; we consume and cross-check. |
| **Real or synthetic owner data** | Recommend synthetic parties, real geometry. The role model gets demonstrated without a privacy incident. |
| **3D export format** | CityGML 3.0 as authoritative exchange, GeoJSON for 2D interop. Its space model maps onto our unit types. |

## Gaps in our own model, not yet built

| Item | Why it matters |
|---|---|
| **`interest` / RRR table** | Without party + right, this is a geometry store, not a cadastre, and PRD §2's dispute-reduction purpose is unreachable. Manual or CSV populated; deed *parsing* stays out of scope. See `01-prd-analysis.md` §2. |
| **Explicit split/merge events** | `created_from` and `replaced_by` exist, but there is no n:m event with `predecessor_ids[]`/`successor_ids[]`. Without it a chain of title cannot be traced. |
| **Evaluation set and metrics** | AI is in the loop with no metrics, so `confidence_score` currently has no calibrated meaning. Needs a hand-delineated hold-out reporting footprint IoU, storey-count exact match, volumetric IoU. |
| **The fixture has no unknown-height unit** | Every one of the 16 units in `demo-parcel.json` has a height, so the FR-03 path — `lower_limit: null`, which P5 renders as a grey marker slab and P1 counts on the dashboard — is never exercised by the committed fixture. Found when writing the export tests. It *is* exercised live: every unit imported from P2 takes exactly that path, because no DEM/DSM reaches the GeoPackage. Adding one to the generator changes the unit count that several tests and P5's demo assert, so it needs a deliberate pass rather than a drive-by edit. |
| **P2 delivers no rasters** | `file_inspector` reads a GeoTIFF's CRS, bounds and resolution, but `process_file` then calls `gpd.read_file` unconditionally, so a `.tif` passes inspection and fails on read. The `raster` registry table is created and stays empty. Consequence: `extrude` cannot run on real data and every imported building has an unknown height. P2 owns this; we consume. |

## Team-level, not ours to decide alone

- **There are two P5 viewers.** `viewer/` consumes the committed contract; `phase5/` uses
  its own WGS84 GeoJSON, pins the maplibre version known to blank the map, and holds the
  Netlify config. Only `viewer/` was wired to the live endpoint, because only it speaks
  the contract — but which is the deliverable has not been decided, and building
  downstream against both is not possible. See `blocks/p5-viewer.md`.
- ~~**P3 and P6 have no owner.**~~ Resolved: P3 is soumyadipta (`sidecar/ai/`), P6 is
  rudraksha (`web/`). Both blocks are in the repository and both are wired into the
  chain — see `blocks/p3-ai.md` and `blocks/p6-web.md`.
- **No CI runs outside `sidecar/cadastre/**` and `contracts/**`.** `cadastre.yml` is
  scoped there on purpose and says so. Nothing checks P1, P2, P3, P5 or P6 on push, so
  `web/`'s `pnpm test` and every TypeScript build are green only as long as someone runs
  them locally. Each block owning its own workflow is the obvious answer; whose job it is
  to write them has not been agreed.
- **The demo publishes synthetic elevation.** `run_chain.py` registers a generated DEM/DSM
  because P2 delivers no rasters (see above), and `make_demo_rasters.py` labels the source
  `generated - not a survey`. Nothing in the published site currently repeats that label,
  so a judge reading the record sees derived storey heights with no indication that the
  terrain under them was simulated. Surfacing source provenance in the extract panel is
  the fix; it needs P5's DetailsPanel to render `source_ids` against the `source` table
  rather than as bare ids.
- **Build phases have no dates.** With 20 September as the first checkpoint, Phase 1
  should be days, not weeks.
- **Team name** — still undecided. Repo is `groundup`.
