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

```
ground_level = median(DEM inside footprint)
roof_level   = percentile(DSM inside footprint, 90)
```

Both choices are deliberate and must not be "simplified" later:
- **median for ground**, not mean — resists vegetation and DEM edge artefacts
- **p90 for roof**, not max — max catches antennas, water tanks, lift machine rooms and
  parapets, inflating every building by 2–4 m

### Floor splitting

```
usable       = (roof - parapet_deduction) - (ground + plinth_offset)
floor_height = usable / floor_count
floor[i]     = [base + i*fh, base + (i+1)*fh]
```

Two corrections specifically right for Indian construction, both **project parameters,
not constants**:
- **plinth_offset** — buildings sit 0.3–1.0 m above surrounding ground, so the ground
  floor slab is not at DEM level
- **parapet_deduction** — the DSM roof includes a ~1 m parapet wall; without this every
  floor comes out systematically short

Gate: a resulting floor height outside 2.4–5.0 m emits a **Warning**. That band covers
effectively all residential and commercial construction.

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
