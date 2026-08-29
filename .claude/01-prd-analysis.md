# PRD analysis

The team PRD (`SIH26011_PRD.pdf`, 10 pp.) is well written — it reads in the register of a
system that must be *audited*, not demoed. Three of its lines are the correct invariants
and are treated here as hard architectural constraints, not features:

- **FR-03**: *"If height or floor data is missing, the system should show it as missing.
  It must not quietly guess the value."*
- **FR-05**: *"An AI suggestion must stay temporary until a user reviews it."*
- **FR-06**: *"An issued ULPIN must not be given to another unit, even after the old unit
  is closed."*

Most teams will build a system that guesses, auto-approves, and recycles identifiers.

## Gaps found, and what we did about them

### 1. FR-06 contains a contradiction — RESOLVED

Two bullets pull opposite ways:
- *"create the same ULPIN when the same input and settings are used again"* → **derived**
- *"an issued ULPIN must not be given to another unit"* → **allocated**

You cannot have both on one field. If the identifier is a function of geometry, then a
2 cm refinement of the point cloud mints a *different* ULPIN for the *same physical flat*,
destroying the entire purpose of a persistent property identifier.

**Resolution — split identity from locator:**

| Field | Nature | Lifetime |
|---|---|---|
| `unit_id` | Opaque, allocated once, never derived, never reused | Immutable forever |
| `ulpin` | Derived, **stamped at approval then frozen** | Bound to `unit_id` permanently |
| `ulpin_provisional` | Recomputed freely | Discarded at approval |

Determinism applies to the *minting function*, not the lifetime binding. **Approval
freezes the binding** — that is the load-bearing sentence of the whole system, and it is
enforced in the database by
`CHECK (status <> 'approved' OR ulpin IS NOT NULL)`.

### 2. The PRD models space but not rights — PARTIALLY ADDRESSED

PRD §7 has property unit, source data, check result, history event. There is **no party
and no right**. LADM is built on a three-way spine:

```
LA_Party ──has──> LA_RRR ──over──> LA_SpatialUnit
 (who)      (right/restriction/       (where)
             responsibility)
```

We have only the third. That makes it a 3D geometry store, not a cadastre, and PRD §2's
stated purpose (reducing property disputes) is unreachable without the other two.

PRD §4.2 correctly excludes *automatic deed parsing* — keep that exclusion. But excluding
automatic extraction is different from excluding the data model. **An `interest` table
(party ref + right type + spatial unit ref + share fraction + evidence document ref),
populated manually or by CSV, is still to be added.** See `08-open-questions.md`.

### 3. No temporal model — ADDRESSED in the schema

FR-09 versions approved records, but §7.1 has only `created_at / updated_at /
approved_at` — **transaction time only**. Missing is **valid time**: when the change
happened in the world. A building demolished March 2024 but recorded August 2025 has two
different dates, and every dispute turns on which one you mean.

Our `unit` record carries all four: `valid_from`/`valid_to` (true on the ground) and
`recorded_from`/`recorded_to` (when the system believed it). LADM's `VersionedObject`
does the same.

### 4. Split and merge have no first-class representation — PARTIALLY ADDRESSED

Flats get combined, floors subdivided, parcels split. FR-04 lists `created from` and
FR-06 has a `replaced` status, so it is half there — but there is no explicit split/merge
event with n:m lineage. Without it you cannot trace a chain of title.

`unit_relationship` supports `created_from` and `replaced_by`. An explicit
split/merge event type with `predecessor_ids[]` / `successor_ids[]` is still to be added.

### 5. `lower_limit` / `upper_limit` is too weak — ADDRESSED with a stated limitation

That pair assumes every unit is a **prism**. Real ones are not: mezzanines, double-height
rooms, stepped terraces, cantilevered balconies, spiral ramps, sloping roofs.

We keep the interval as the authoritative geometry for v1 and carry a `representation`
flag (`prism` | `polyhedron`) so polyhedral units are a clean later extension. The
limitation is stated deliberately — see `02-architecture.md`.

### 6. Vertical datum is treated as a config value — IT IS A MODULE

PRD §11 asks *"which height reference should be used?"* as though it were a setting. It
is three incompatible height systems that must be reconciled:

| Source | Height system |
|---|---|
| LiDAR, photogrammetry, GNSS | Ellipsoidal (WGS84) |
| Survey of India topo, DEM | Orthometric (MSL, via a geoid model) |
| Building floor plans | **Local** — "finished floor level = 0.000" |

Get this wrong and a whole building sits tens of metres off vertically **while every
internal relationship still validates cleanly** — the worst class of bug, because
relative checks cannot see a uniform offset. This is P2's responsibility; our contract
makes `vertical_datum` mandatory per source and we raise `DATUM_MISMATCH` when sources
disagree. We cannot detect a uniform offset applied to everything.

### 7. `validation_state` conflated two axes — ADDRESSED

Geometric validity ("this solid is not watertight") and legal contestation ("two parties
claim this volume") are different. A cadastre must be able to *hold* a contradiction
without resolving it. Split into `validation_state` and `dispute_state`.

### 8. Underground modelled as ownership — ADDRESSED

Utilities and tunnels are **easements / way-leaves**, not ownership volumes. That is both
legally correct in India and computationally convenient:

- ownership volumes **must not** overlap → topology error
- easement corridors **are expected to** overlap the parcels they run under → normal

Modelling both as one class makes the overlap check scream on every correctly-modelled
utility line. `UnitType.is_easement` encodes the distinction.

### 9. Smaller gaps

- **"10,000 units" is too small.** A mid-sized Indian ward is 50k–200k units.
- **No accuracy or evaluation section.** AI is in the loop with no metrics, which makes
  `confidence_score` a number with no meaning. Needed: a hand-delineated hold-out set
  reporting 2D footprint IoU, storey-count exact-match rate, and volumetric IoU.
- **Missing risk:** *geometry is plausible but wrong and a tired reviewer approves it.*
  Mitigation is a UI decision — the review screen must show the **evidence** (the actual
  point-cloud vertical slice beside the proposed slab lines), not just the resulting
  polygon. This is the difference between real human-in-the-loop and rubber-stamping.
