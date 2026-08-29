# Working conventions

## Git identity — automatic, never switch accounts

This machine carries two GitHub identities. Routing is **by remote URL, not directory**,
so it survives fresh clones anywhere on disk.

```ini
# ~/.gitconfig, appended at the END so it wins over the global [user] block
[includeIf "hasconfig:remote.*.url:git@github.com-slashexx:*/*"]
	path = ~/.gitconfig-slashexx
```

| Context | Identity | Signing key |
|---|---|---|
| remote uses `github.com-slashexx` alias | `slashexx` / `dhruvpuri.35@gmail.com` | `80584758E11CC4F9` |
| any other remote, or none | `dhruvpuri-aspora` | `27C7BE…41FAACF7` |

> **`**` is NOT supported in `hasconfig` URL patterns — only `*/*`.** The first attempt
> used `**`, matched nothing, and failed *open* to the work identity, which is the
> dangerous direction. If another alias is added, copy the `*/*` form and verify with
> `git config --show-origin user.email`.

`gh` is wrapped in `~/.config/fish/functions/gh.fish`, which picks the token from the
repo's remote (or from a `slashexx/...` argument) — no `gh auth switch`, ever.
`pclone <repo>` clones a personal repo with the alias URL already wired up.

Backup of the original global config: `~/.gitconfig.bak-20260829`.

## Commits

- Conventional commits: `feat(cadastre):`, `fix(ulpin):`, `docs:`, `chore:`
- Atomic. Every commit must import cleanly and pass tests.
- **GPG signed always.** Never pass `--no-gpg-sign`; wait for the key prompt.
- **Never add `Co-Authored-By` trailers.**
- The body explains *why*, and states measured facts (rates, areas, counts) rather than
  adjectives.

## Code

- Functions under ~20 lines, under 3 parameters, pure where possible
- Comments explain **why**, never what
- Type hints everywhere; `from __future__ import annotations` at the top
- Docstrings on every module carry the *design rationale*, so a module can be picked up
  without re-reading conversation history. This is deliberate — keep doing it.
- `ruff`, line length 100

## Testing

- `pytest` for behaviour, **`hypothesis` for geometry invariants** — properties like
  "no two approved sibling ownership units overlap" are exactly what property-based
  testing is for.
- Test behaviour, not implementation. AAA pattern.
- The fixture is the primary integration test input; `expected_findings` and
  `must_not_fire` are the assertions.

## Environment

```bash
python3 -m venv .venv && ./.venv/bin/pip install shapely pytest hypothesis jsonschema
./.venv/bin/python -m pytest sidecar/cadastre/tests -q
```

`.venv/` is git-ignored. `pyproject.toml` under `sidecar/cadastre/` holds the real
dependency list.

## When a decision changes, check `contracts/` first

Our own docs going stale is an inconvenience. **The contract going stale is a defect
delivered to a teammate**, because it is the one file whose staleness propagates into
someone else's code.

This has already happened once. We changed the roof estimator from a high percentile to a
median, which made `parapet_deduction` unnecessary. `.claude/03-design.md` was updated,
the fixture generator was updated, the tests were updated — and
`contracts/inbound/p2-geopackage.md` still said `1.0`. Every artifact we owned was
internally consistent. P2 read the contract, implemented it faithfully, and every building
came out a metre short with every storey 14 cm shy. **All 13 validation rules passed**,
because a uniform offset leaves every relative relationship intact.

So, after any decision that touches a value, a format, a threshold or a field:

1. `grep` the changed name across `contracts/` before anything else
2. update the contract in the **same commit** as the decision
3. record *why* the old value is wrong, not just what the new one is — a bare value gives
   a reader nothing to check their own assumptions against

### Documentation is the weakest possible enforcement

The correct fix for that bug was not editing the markdown. It was making
`extrude.building.build` raise `EstimatorMismatch` on a non-zero deduction, so the bad
configuration cannot be silently accepted by anyone, ever.

Prefer, in order:

| | Mechanism |
|---|---|
| best | make the bad state unrepresentable (a type, an enum, a required field) |
| good | refuse it at runtime with a message naming the setting and the correct value |
| weak | a schema constraint that only fires if someone validates |
| worst | a sentence in a document, and hope |

A rule that lives only in prose has already failed once here. When a wrong value would be
**silent** — producing plausible output that passes every check — prose is never
sufficient.

## Mutation testing

After changing any rule or threshold, delete the guard it depends on and confirm the
suite goes red. A rule whose removal keeps the tests green is not being tested. See the
battery in `05-validation.md` — it has already caught one vacuous negative test and one
wrong threshold that a fully-passing suite had missed.

## Regenerating the fixture

```bash
python3 sidecar/cadastre/tools/make_fixture.py
```

**Edit the generator, never the JSON.** The JSON is committed output so downstream teams
can consume it without running our code.

## Verifying the ULPIN check character

If `_running_sum` is ever refactored, re-run the detection measurement (see
`04-ulpin.md`). A subtly wrong check character still looks like it works.
