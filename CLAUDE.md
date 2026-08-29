# groundup · cadastre

3D ULPIN generation and vertical property mapping.
SIH 2026 · **SIH26011** · Ministry of Rural Development, Dept of Land Resources.

**This repository contains only the P4 block (`cadastre/`).** Other blocks are owned by
other people and live in their own folders, added by them. Do not scaffold, design,
prescribe implementation for, or create placeholder files for any block that is not ours.

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

**4. Prefer updating an existing file over creating a near-duplicate.** Keep one home per
topic.

**5. Update `README.md` when the derived summary drifts** from `.claude/`.

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
python3 cadastre/tools/make_fixture.py    # regenerate the fixture (edit the generator, not the JSON)
pytest cadastre/tests                     # tests
ruff check cadastre                       # lint
```

Ownership inside the block: **dhruv** owns rasters and spatial predicates (`extrude/`,
`validate/`); **shankhanil** owns identity, process and schema (`ulpin/`, `api.py`,
`validate/rules/metadata.py`). `models.py` and `store.py` are shared.
