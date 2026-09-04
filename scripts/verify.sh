#!/usr/bin/env bash
# Every gate, in one command. If this is green, the cadastre block is sound.
#
# The order is deliberate: cheap and specific first, so a failure points at the smallest
# possible cause. The smoke test runs last because it is the slowest and the least
# specific - it tells you the chain is broken, not which module broke it.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY="${PY:-./.venv/bin/python}"
fails=()

step () {
  local label="$1"; shift
  printf '\n\033[1m── %s\033[0m\n' "$label"
  if "$@"; then printf '\033[92m   passed\033[0m\n'; else fails+=("$label"); printf '\033[91m   FAILED\033[0m\n'; fi
}

step "lint"        "$PY" -m ruff check sidecar/cadastre
step "unit tests"  "$PY" -m pytest sidecar/cadastre/tests -q -W ignore::PendingDeprecationWarning

# The generator is the source; the committed JSON is output that other blocks consume.
step "fixture is generated, not hand-edited" bash -c \
  "$PY sidecar/cadastre/tools/make_fixture.py >/dev/null && git diff --exit-code contracts/fixtures/demo-parcel.json"

# A passing suite proves nothing on its own. Every mutation must turn it red.
step "mutations"   "$PY" sidecar/cadastre/tools/mutation_check.py

# Schemas are consumed by four TypeScript clients; a drifted one is a defect delivered
# to a teammate.
step "contracts"   bash -c "$PY - <<'EOF'
import json, pathlib, sys
from jsonschema import Draft202012Validator as V
root = pathlib.Path('contracts'); ok = True
for p in sorted(root.rglob('*.schema.json')):
    try: V.check_schema(json.loads(p.read_text()))
    except Exception as e: print(f'  invalid {p}: {e}'); ok = False
unit = V(json.loads((root/'outbound/unit.schema.json').read_text()))
fx = json.loads((root/'fixtures/demo-parcel.json').read_text())
bad = sum(1 for u in fx['units'] for _ in unit.iter_errors(u))
print(f'  {len(fx[\"units\"])} fixture units, {bad} violation(s)')
sys.exit(0 if ok and not bad else 1)
EOF"

# The one that has caught every serious defect: they all lived between modules.
step "end-to-end"  "$PY" sidecar/cadastre/tools/smoke.py

printf '\n'
if ((${#fails[@]})); then
  printf '\033[91m%d gate(s) failed:\033[0m %s\n' "${#fails[@]}" "${fails[*]}"; exit 1
fi
printf '\033[92mall gates green\033[0m\n'
