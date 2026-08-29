# groundup · cadastre

3D ULPIN generation and vertical property mapping.
SIH 2026 · **SIH26011** · Ministry of Rural Development, Dept of Land Resources.

**This is the single repository for the whole project.** All six blocks land here and
everyone pushes to it. `.claude/` is the source of truth for the entire project, not just
for our part.

**We own `sidecar/cadastre/`.** Other blocks are added by their owners, at paths they
choose. Do not scaffold, design, prescribe implementation for, or create placeholder
folders for a block that is not ours — not even empty ones. An empty folder is still an
instruction.

```
groundup/
├── CLAUDE.md · README.md · .claude/     project-wide
├── contracts/                           cross-team interfaces (we author ours)
└── sidecar/
    └── cadastre/    ← ours              Python block; siblings arrive from their owners
```

The layout is meant to read sensibly as the repository fills up: `sidecar/` groups the
Python blocks, `contracts/` is the shared interface surface. Nobody's folder is created
in advance.

---

## `.claude/` is the single source of truth

**Every design decision, rationale, specification and piece of project context lives in
`.claude/`.** Not in scattered `docs/` folders, not in code comments, not in commit
messages, not in chat history. If it matters and it is not in `.claude/`, it does not
exist and will be lost.

`README.md` is a derived summary for humans arriving at the repo. It never carries
information that is absent from `.claude/`.

### Read before doing anything

| Read | When |
|---|---|
| **[`.claude/00-project.md`](.claude/00-project.md)** | **Always.** The problem, the domain, who owns what. |
| **[`.claude/07-conventions.md`](.claude/07-conventions.md)** | **Always.** Git identity, commits, code and test conventions. |
| [`.claude/01-prd-analysis.md`](.claude/01-prd-analysis.md) | Touching the data model or questioning a requirement |
| [`.claude/02-architecture.md`](.claude/02-architecture.md) | Any dependency, storage or stack question |
| [`.claude/03-design.md`](.claude/03-design.md) | Working anywhere in `cadastre/` |
| [`.claude/04-ulpin.md`](.claude/04-ulpin.md) | Anything under `cadastre/ulpin/` |
| [`.claude/05-validation.md`](.claude/05-validation.md) | Anything under `cadastre/validate/`, or the fixture |
| [`.claude/06-contracts.md`](.claude/06-contracts.md) | Changing any schema, or an interface with another block |
| [`.claude/08-open-questions.md`](.claude/08-open-questions.md) | Planning, or when something seems unresolved |
| [`.claude/blocks/p2-ingest.md`](.claude/blocks/p2-ingest.md) | Working in `sidecar/ingest/` (P2 Geo Data Pipeline), or consuming it |
| [`.claude/blocks/p5-viewer.md`](.claude/blocks/p5-viewer.md) | Working in `viewer/` (P5 components), or consuming them |

### Planned: per-block segregation

The flat files above are **cross-cutting context** and stay that way. Once other blocks
land in this repository and integration begins, add a `blocks/` subfolder:

```
.claude/
├── 00-…-08-…            cross-cutting context (unchanged)
└── blocks/
    ├── p1-desktop.md    shell and review UX
    ├── p2-ingest.md     geo pipeline, CRS and datum harmonisation
    ├── p3-detect.md     building extraction, floor estimation
    ├── p4-cadastre.md   ours — pointer into 03/04/05, not a duplicate
    ├── p5-viewer.md     Cesium + MapLibre components
    └── p6-web.md        static export and publish
```

Each block file records **owner · scope · the interface with us · observed current state ·
decisions specific to that block**. Create a file the moment a block becomes something we
interact with, and add it to the table above in the same commit.

> **Record, do not prescribe.** For blocks that are not ours, capture what has been
> *agreed at the interface* and what is *observably true* — never how we think they should
> build it. That distinction is why this repository contains only `cadastre/`.

Cross-cutting information stays in the numbered files. A fact that concerns two or more
blocks does not belong in `blocks/`.

---

## Maintenance rules — not optional

**1. Keep `.claude/` current with every crucial piece of information.**
After any of the following, update the relevant file *in the same commit as the change*:

- a design or architecture decision is made, changed, or reversed
- a requirement is reinterpreted, or a contradiction in the PRD is resolved
- an algorithm, threshold, tolerance or constant is chosen — record the *reason*
- an interface with another block is agreed or altered
- an assumption is invalidated, or a bug reveals a wrong belief
- an option is considered and **rejected** — record it and why; rejected options are
  asked about by reviewers and judges
- a measured fact is established (detection rates, areas, counts, timings)
- an open question is answered

**2. Create the file if it is not there.** If a new area of concern emerges that no
existing file covers, add `.claude/NN-topic.md` and add a row to the table above in the
same commit. Never let context fall on the floor because there was nowhere obvious to put
it.

**3. Record corrections, not just conclusions.** When something was believed and turned
out wrong, write down both the wrong belief and how it was caught. Two examples already in
here: the parent ULPIN being 14 characters and not 16, and `**` being unsupported in
git `hasconfig` patterns. Those notes stop the same mistake recurring.

**4. Split into `.claude/blocks/` when the repository grows past our block.** See
*Planned: per-block segregation* above. Until then, per-block files would be speculative,
so do not create them early.

**5. Prefer updating an existing file over creating a near-duplicate.** Keep one home per
topic.

**6. Update `README.md` when the derived summary drifts** from `.claude/`.

---

## Hard invariants

These come from the PRD and are architectural constraints, not features. Do not weaken
them for convenience.

1. **Never guess a missing value.** If height or floor data is absent, represent it as
   absent (`None`, `subdivided: false`). FR-03.
2. **AI output stays provisional until a human reviews it.** We consume only suggestions
   with `review.state` of `accepted` or `edited`. FR-05.
3. **An issued ULPIN is never reused**, not even after the unit is closed. Proven by the
   append-only `ulpin_ledger`. FR-06.
4. **Approval freezes the ULPIN binding.** `unit_id` is identity; `ulpin` is a locator
   stamped at approval. Enforced by a DB `CHECK` constraint.
5. **Sequence numbers are allocated once and locked**, never re-derived from geometry.
6. **Tolerances are derived from source accuracy**, never hardcoded.
7. **Containment is type-conditional.** Easements are supposed to cross parcels;
   ownership volumes are not.

---

## Quick reference

```bash
python3 sidecar/cadastre/tools/make_fixture.py    # regenerate the fixture (edit the generator, not the JSON)
pytest sidecar/cadastre/tests                     # tests
ruff check sidecar/cadastre                       # lint
```

Ownership inside the block: **dhruv** owns rasters and spatial predicates (`extrude/`,
`validate/`); **shankhanil** owns identity, process and schema (`ulpin/`, `api.py`,
`validate/rules/metadata.py`). `models.py` and `store.py` are shared.
