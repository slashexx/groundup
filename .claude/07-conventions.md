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
dependency list. The same venv runs all three Python blocks — P2 and P3 import from it
too, and `run_chain.py` calls them in-process rather than over HTTP.

The three JavaScript blocks each install separately: `desktop/` on npm, `viewer/` and
`web/` on pnpm. `web/` needs `viewer/` installed as well, because `@viewer` aliases
`../viewer/src/lib` and those sources resolve their bare imports against
`viewer/node_modules` — see `blocks/p6-web.md`.

**P1 packages as a native Tauri app and that needs a Rust toolchain.** Without `cargo`,
`npm run tauri dev` fails and `npm run dev` serves the same React app in a browser on the
same port, with the same sidecar wiring. Nothing in the review UX depends on the native
shell, so a machine without Rust can still run and demonstrate the whole chain.

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
suite goes red. A rule whose removal keeps the tests green is not being tested.

The battery is executable, not a checklist: `tools/mutation_check.py` holds 14 mutations,
applies each one, and asserts the suite fails. Add an entry whenever you add a guard. A
`STALE` result means the code moved and the mutation no longer matches anything — treat
that as a failure too, because it means the guard is unverified.

It has already caught three real defects that a fully-passing suite had missed: a vacuous
negative test, a perimeter-scaled threshold that let a corridor escape its parcel, and a
provisional ULPIN whose sequence was never reserved.

## CI

`.github/workflows/cadastre.yml`, scoped by path to `sidecar/cadastre/**` and
`contracts/**`. Three jobs:

| Job | Checks |
|---|---|
| `tests` | fixture regenerates identically, rasters build, pytest, ruff |
| `mutations` | all 14 mutations turn the suite red |
| `contracts` | every schema is valid Draft 2020-12 and every fixture unit satisfies it |

Other blocks add their own workflows. This one is deliberately not a template for them.

## Regenerating the fixture

```bash
python3 sidecar/cadastre/tools/make_fixture.py
```

**Edit the generator, never the JSON.** The JSON is committed output so downstream teams
can consume it without running our code.

## Verifying the ULPIN check character

If `_running_sum` is ever refactored, re-run the detection measurement (see
`04-ulpin.md`). A subtly wrong check character still looks like it works.
