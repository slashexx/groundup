# ULPIN specification

## Format

```
KA05B012345678 - V1 - A07 - 003 - K
└─────┬──────┘   └┬┘  └┬┘   └┬┘   └┬┘
 parent 2D ULPIN  │    │     │     └ ISO 7064 MOD 37,36 check character
 (14 chars,       │    │     └ unit sequence on that level (000 = whole level)
  untouched)      │    └ stratum letter A|S|B + 2-digit level
                  └ scheme version
```

Machine-readable form, required by FR-06:
```
urn:ulpin:3d:v1:KA05B012345678:A:07:003
```

Strata: `A` above ground, `S` surface, `B` below ground.

## Why each field exists

- **The 14-char prefix is preserved untouched** so every existing Bhu-Aadhaar record still
  resolves, and a lexical sort naturally groups units by parcel.
- **The stratum letter** is readable at a glance without a lookup table.
- **The version field** exists because FR-06 explicitly requires the format to change when
  DoLR publishes the official specification. It is not decoration.
- **The check character** catches transcription errors, the same reason Aadhaar carries a
  Verhoeff digit.

> **The parent ULPIN is 14 characters, not 16.** An earlier draft of our own design doc
> used a 16-character sample and the format validator caught it. If a sample string
> anywhere fails `PARENT_RE`, the sample is wrong, not the code.

## Check character

ISO 7064 MOD 37,36 over the alphabet `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ`.
Implemented in `sidecar/cadastre/ulpin/encode.py` and **verified empirically, not assumed**:

| Error class | Detection rate |
|---|---|
| single-character substitution | **100.00%** |
| adjacent transposition | **99.89%** |

Measured over 200 random 24-character bodies. A well-formed string has running-sum
residue **2** under `_running_sum`; that is the verification predicate.

The first implementation attempt scored only 97% because the modular reduction was applied
in the wrong order. If anyone refactors `_running_sum`, **re-run the detection measurement**
— a subtly wrong check character still looks like it works.

## The determinism trap — the subtle part

FR-06 asks for "same input → same ULPIN". Where does the `003` come from?

Spatially sorting units on a level (north→south, west→east) is deterministic — but
**inserting one unit renumbers every unit after it**, silently changing the identity of
flats people already own. Catastrophic for a property register.

**Therefore: the sequence is computed once at first mint, written to `ulpin_sequence`, and
locked.** Determinism means *"recomputing over the same input set yields the same answer"*,
not *"the number is recomputed forever."*

This is the identity-vs-locator split (see `01-prd-analysis.md` §1) reappearing one level
down. `ulpin_sequence` is deliberately a separate table from `ulpin_ledger` for this reason.

*Considered and rejected:* deriving the discriminator from a hash of the centroid rounded
to 0.5 m. Stable against insertion, but unreadable and admits collisions. Have this answer
ready — it is a natural question from an informed judge.

## Lifecycle

```
draft ──> processing ──> needs_review ──> approved ──> replaced
  ^            │               │              │
  └──(fail)────┘               │              └──────> closed
  └──────────(reject + comment)┘
```

| Transition | Guard | Side effect |
|---|---|---|
| draft → processing | job accepted | — |
| processing → needs_review | job complete | run validation |
| processing → draft | job failed | record error, leave prior record intact |
| **needs_review → approved** | **a validation run exists AND it has zero Errors AND every Warning is acknowledged** | **freeze ULPIN, write ledger row** |
| needs_review → draft | reviewer rejects | store comment |
| approved → replaced | a successor exists | link `replaced_by`, ledger `state=replaced` |
| approved → closed | decommissioned | ledger `state=closed`, ULPIN retained forever |
| closed → anything | — | forbidden |

**An approved record is never edited.** Any change creates a new version.

ULPIN presence by status:

| Status | `ulpin_provisional` | `ulpin` |
|---|---|---|
| draft / processing / needs_review | recomputed freely | NULL |
| approved | discarded | assigned, in ledger, frozen |
| replaced | — | retained; successor gets a *new* one |
| closed | — | retained forever, never reissued |


## The approval guard fails closed

`transition` loads the latest persisted run itself when one is not passed in. If **no run
has ever been recorded, approval is refused** — an absent run means *we cannot verify this
unit*, never *there is nothing to verify*.

That distinction was originally a bug. The guard read
`if validation_run is not None and not validation_run.approvable(...)`, so passing nothing
skipped the check entirely — and the API passed nothing, because findings were computed in
memory and never persisted. A unit whose `validation_state` was `failed` could be approved
through the HTTP surface and receive a permanent identifier.

This is the same shape as two other defects recorded in these notes: the `hasconfig` glob
that matched nothing and fell back to the wrong git identity, and the stale contract that
produced plausible-but-wrong heights. **In each case the code did something reasonable
when information was missing, instead of stopping.** For a register that mints permanent
identifiers, missing information is a refusal.

Errors are additionally **not acknowledgeable**. A reviewer may accept a warning; an error
must be corrected and validation re-run. `store.acknowledge_finding` rejects it, and the
API returns 409.
