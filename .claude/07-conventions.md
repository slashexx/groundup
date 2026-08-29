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
