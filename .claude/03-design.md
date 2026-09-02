# Cadastre module design

## Layout and ownership

```
cadastre/
  models.py            dataclasses mirroring the JSON Schemas       [BOTH, day 1]
  store.py             sqlite3 over the .gpkg: six tables           [BOTH, day 1]
  loader.py            bundle/fixture JSON -> domain objects        [BOTH]
  api.py               FastAPI router                               [shankhanil]

  extrude/                                                          [dhruv]
    raster.py          zonal stats over a footprint mask
    building.py        footprint + DEM/DSM -> building unit
    floors.py          building -> N floor units
    subdivide.py       floor -> apartments

  ulpin/                                                            [shankhanil]
    encode.py          mint, format, ISO 7064 check char   [COMPLETE]
    ledger.py          allocation, freeze-on-approval, non-reuse proof
    lifecycle.py       state machine + guarded transitions

  validate/
    engine.py          rule registry + run orchestration            [dhruv]
    context.py         STRtree, containment graph, per-unit accuracy [dhruv]
    tolerance.py       provenance -> tolerance                      [dhruv]
    rules/_util.py     finding builder, z_overlap, shrink            [dhruv]
    rules/
      geometry.py      invalid, duplicate, impossible z             [dhruv]
      overlap.py       sibling overlap, gap vs parent               [dhruv]
      containment.py   escapes parent, type-conditional             [dhruv]
      sequence.py      floor ordering and contiguity                [dhruv]
      metadata.py      provenance completeness, CRS/datum           [shankhanil]

  contracts/           JSON Schemas, in and out
  fixtures/            -> contracts/fixtures/demo-parcel.json
  tools/               make_fixture.py
  tests/
```

**The seam: dhruv owns everything touching rasters and spatial predicates; shankhanil owns
everything touching identity, process and schema.** `models.py` and `store.py` are built
together on day 1; after that the two halves share no code, only the `unit` table.

Difficulty ranking used to assign the split (hardest first): validation engine, extrusion
engine, ULPIN ledger, relationship graph, findings model, schemas.

## Data model

Six tables, all inside the project `.gpkg`. Full DDL in `sidecar/cadastre/store.py`.

**`unit`** — the identity split is the important part. `unit_id` is opaque and permanent;
`ulpin` is NULL until approval, then frozen. Enforced by
`CHECK (status <> 'approved' OR ulpin IS NOT NULL)`.

**`unit_relationship`** `(from, to, rel_type, created_at)` where rel_type is
`contains | inside | overlaps | adjacent | created_from | replaced_by`. Traversed with
recursive CTEs. **Not** a parent pointer — `created_from` and `overlaps` are many-to-many
and any merge of two flats breaks a tree.

**`ulpin_ledger`** — append-only, never deleted. How FR-06's non-reuse guarantee is
*proven*, including for closed units.

**`ulpin_sequence`** — deliberately separate from the ledger. See `04-ulpin.md`; this is
what stops sequence numbers being re-derived.

**`validation_run`** and **`finding`** — findings belong to a run; the latest run for a
unit determines its `validation_state`, which gives validation history for free.

## The six unit types are not variations of one thing

They differ in z-semantics and in what containment *means*:

| Type | z-extent from | Must sit inside its parcel? |
|---|---|---|
| `land_parcel` | project stratum limits (e.g. −30 m to +150 m) | it *is* the parent |
| `building` | ground → roof, from DEM/DSM | yes |
| `floor` | slab to slab, computed | yes |
| `apartment` | inherits its floor's z-range | yes |
| `underground_feature` | depth range, buffered line | **no — crosses many parcels** |
| `elevated_structure` | above ground, spans parcels | **no — crosses many parcels** |

That last column is the point. **Containment is a check, not an assumption**, and the
expected answer flips by type. A single "child must be inside parent" rule generates false
errors on every utility and flyover in the dataset. Encoded as `UnitType.is_easement`.

## Extrusion algorithms

### Zonal statistics

**Both ground and roof use the median.** Measured against synthetic rasters with planted
truth (slab 934.0, ground 912.4):

| estimator | DSM error | DEM error | why it fails |
|---|---|---|---|
| mean | +0.15 m | +0.20 m | dragged by outliers |
| p90 | +0.97 m | +1.09 m | lands on the parapet |
| max | +6.00 m | +2.52 m | lands on the water tank |
| **median** | **0.00 m** | **0.00 m** | finds the dominant plane |

A DSM over a flat roof is bimodal: a large slab plane plus a small parapet ring, with
point features (water tanks, lift machine rooms, antennas) on top. The slab is the
dominant area for any real building, so the median finds it and rejects everything else
**regardless of building size**. A DEM has no real observations beneath a roof, so values
there are interpolated and carry artefacts; the median ignores them.

> **Correction — this reverses an earlier decision.** The original design took the 90th
> percentile of the DSM and subtracted a `parapet_deduction` constant. Building the
> synthetic rasters exposed the flaw: the parapet's share of roof area depends on the
> building's dimensions, so the correct percentile differs for every structure. In the
> demo building the parapet was 9.5% of roof area, so p90 landed on it only because the
> water tank pushed the combined fraction past 10%. A slightly larger building would have
> silently returned the slab and then subtracted a parapet that was never included,
> producing an answer 1 m low with nothing to indicate it.
>
> The median removes both the magic constant and the fragility.
> `default_parapet_deduction_m` is retained in settings as an escape hatch for sloped
> roofs and is **0.0** for the median estimator.

### Floor splitting

```
usable       = roof_slab - (ground + plinth_offset)
floor_height = usable / floor_count
floor[i]     = [base + i*height, base + (i+1)*height]
```

**plinth_offset** is specifically right for Indian construction: buildings sit 0.3-1.0 m
above surrounding ground, so the ground floor slab is not at DEM level. A project
parameter, not a constant.

Floors are computed from a single base rather than accumulated, so rounding drift cannot
make consecutive floors fail `FLOOR_SEQUENCE`. A 0.1% drift injected as a mutation does
break the test, which is the point.

Gate: a floor height outside 2.4-5.0 m is **reported, never silently corrected**.
Validation raises the warning and a human decides - a 5.5 m ground floor is normal for
retail.

### Refusing to guess

`raster.NoCoverage` is raised, not defaulted, when a footprint has no valid pixels.
`building.build` leaves `lower_limit`/`upper_limit` as `None` when coverage falls below
`MIN_COVERAGE = 0.6`, and records `heights_unavailable`. Downstream, `floors.split`
raises `NotExtrudable` rather than inventing a range. That chain is FR-03 made
structural rather than aspirational.

### Apartment subdivision — the honest answer

We usually have no interior geometry. In order of preference:

1. **Floor plan available** → vectorise and apply; a repeating tower may reuse one plan
   across floors. Mark `created_by=derived`, low confidence, requires review.
2. **Manual delineation** in the UI — used for the demo building.
3. **Nothing** → do **not** create apartment units. Set `attributes.subdivided = false`.

Path 3 is the default, and it is what FR-03 requires. Fabricating apartments across the
dataset is the fastest way to lose a judge who knows this domain.

## Why the extrusion stage is rule-based, not learned

Percentiles, a division and two constant offsets. This is not a shortcut. FR-05 requires a
human to review and accept each suggestion, and a reviewer can meaningfully interrogate
*"we took the 90th percentile of the DSM and subtracted a 1 m parapet."* They cannot
meaningfully interrogate a regression head's output. Confining ML to P3's outline
*detection*, where it earns its keep, is what makes human-in-the-loop real rather than
ceremonial.

## Sequencing

1. **Foundations** — `models.py` + `store.py` together; publish the schemas; ship the
   fixture. The fixture unblocks P5's viewer, P6's export and P1's review screen before a
   line of real geometry code exists.
2. **Core** — extrude → ulpin → validate, in that order; each feeds the next.
3. **Integration** — wire into the review screen, viewer and export.
4. **Polish** — tune tolerances against the real demo dataset.

> Start with `validate/`, not `extrude/`. The fixture already provides its complete input
> and expected output, so the engine can be written test-first and be green before any
> raster code exists.

## Attaching a footprint to its parcel

`ingest_gpkg.MAJORITY = 0.5`. A building is assigned to a parcel only when that parcel
holds **strictly more than half** of the footprint's area.

The obvious rule — attach to any parcel the footprint `intersects` — makes almost every
building ambiguous. Footprints and parcel boundaries come from different sources with
different accuracies, so a metre of slop along a shared boundary is the normal case, and
that sliver clips the neighbour. A reviewer who has to dismiss an ambiguity on every
single building stops reading them, which is the same failure mode tolerance derivation
exists to prevent.

A majority share has a property a "largest share wins" rule does not: **two parcels
cannot both hold more than half of the same footprint**, so the winner is unique by
construction and there is never a tie to break by preference or read order. A building
genuinely straddling a boundary reaches no majority anywhere and is reported unresolved
with the largest share it did find — which is the honest answer, and the case a human
should look at.

`parcel_local_id`, when P2 supplies one, takes precedence: P2 knows something we do not.
When it names a parcel that is not in the file, that is **reported, not silently replaced
with a spatial guess** — the mismatch is the interesting fact, and quietly resolving it
would hide a real defect in the upstream data.

## Validation state is written back, not just computed

`store.save_run` updates `unit.validation_state` for every unit the run covered.

This was missing: the run and its findings were persisted, but the column stayed at its
`unvalidated` default forever. The column is outbound contract surface — it is what P5
colours the map by and what P1's review queue sorts on — so a project with three errors
was displayed everywhere as one that had never been checked. The findings were right and
invisible.

`save_run` takes the unit ids the run actually covered. Without them the run is treated
as project-wide, which is what `validate.run` does today. **A scoped run must pass its
own ids**: marking a unit passed on the strength of a run that never looked at it is the
same class of error as approving one with no run at all, and `lifecycle.transition`
consults exactly this state.
