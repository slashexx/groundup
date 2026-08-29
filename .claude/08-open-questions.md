# Open questions

Live list. Resolve items here and move the outcome into the relevant context file.

## Blocking nothing yet, but decide before Phase 2 ends

| Question | Notes |
|---|---|
| **Official ULPIN format** | Our scheme extends the 14-char parent and carries a version field precisely so this can change. Verify the internal field layout against DoLR's published ULPIN guidelines. |
| **Pilot city and dataset** | Suggested: a Bengaluru or Pune ward with dense apartment stock **and an operating metro line**, which gives a genuine sub-surface case. Build the pipeline on open foreign LiDAR (AHN, Dublin ALS) because it is clean and classified; demo the registry on the Indian site. |
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

## Team-level, not ours to decide alone

- **P3 and P6 have no owner.** P3 is the highest technical risk in the plan; P6 owns the
  pitch. Noted, deferred by team decision since both sit downstream.
- **Build phases have no dates.** With 20 September as the first checkpoint, Phase 1
  should be days, not weeks.
- **Team name** — still undecided. Repo is `groundup`.
