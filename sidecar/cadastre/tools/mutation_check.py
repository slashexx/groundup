#!/usr/bin/env python3
"""Verify the test suite can fail.

A passing suite proves nothing on its own. This applies each mutation below - a
deliberate removal of one guard - and asserts the suite goes red. Any mutation that
leaves it green marks a rule nobody is actually testing.

This is not hypothetical bookkeeping. Two real defects were found this way after the
suite was already passing: a negative test that asserted silence arising from the wrong
cause, and an area threshold that let a 90 m utility corridor leave its parcel
unreported.

    ./.venv/bin/python sidecar/cadastre/tools/mutation_check.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[1]

#: (file, snippet to remove or replace, replacement, what it should catch)
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("validate/rules/_util.py",
     "return max(a.lower_limit, b.lower_limit) < min(a.upper_limit, b.upper_limit) - tol_v",
     "return max(a.lower_limit, b.lower_limit) <= min(a.upper_limit, b.upper_limit) + tol_v",
     "touching floors counted as overlapping"),
    ("validate/rules/overlap.py",
     'if not parent.attributes.get("subdivided"):', "if False:",
     "unmodelled interiors reported as gaps"),
    ("validate/rules/overlap.py",
     "if other.unit_type.is_easement or ctx.parent.get(uid) != ctx.parent.get(oid):",
     "if ctx.parent.get(uid) != ctx.parent.get(oid):",
     "utilities reported against every parcel above them"),
    ("validate/rules/containment.py",
     ("        if u.unit_type.is_easement:\n            continue"
      "                        # an easement leaving its parcel is expected\n"),
     "",
     "easements flagged for leaving their parcel"),
    ("validate/rules/containment.py",
     "PENETRABLE = (UnitType.FLOOR, UnitType.APARTMENT)",
     "PENETRABLE = (UnitType.FLOOR, UnitType.APARTMENT, UnitType.BUILDING)",
     "duplicate findings against aggregates"),
    ("validate/tolerance.py",
     ("return k * math.hypot(a.horizontal_m, b.horizontal_m), "
      "k * math.hypot(a.vertical_m, b.vertical_m)"),
     "return 10.0, 10.0",
     "provenance-derived tolerance bypassed"),
    ("extrude/raster.py",
     "return float(np.median(sample(dsm_path, footprint)))",
     "return float(np.percentile(sample(dsm_path, footprint), 90))",
     "parapet mistaken for the roof slab"),
    ("extrude/raster.py",
     "return float(np.median(sample(dem_path, footprint)))",
     "return float(np.mean(sample(dem_path, footprint)))",
     "DEM interpolation artefacts skewing ground level"),
    ("validate/engine.py",
     '    ("geometry.heights_unavailable", geometry.heights_unavailable),\n', "",
     "a unit with no vertical extent passing validation clean"),
    ("extrude/building.py", "MIN_COVERAGE = 0.6", "MIN_COVERAGE = 0.0",
     "heights invented from a handful of pixels"),
    ("extrude/building.py",
     "    if settings.default_parapet_deduction_m:", "    if False:",
     "a stale parapet setting lowering every floor"),
    ("extrude/floors.py",
     "lower = building.lower_limit + i * height",
     "lower = building.lower_limit + i * height * 1.001",
     "rounding drift breaking floor contiguity"),
    ("extrude/subdivide.py", "lower_limit=floor.lower_limit,",
     "lower_limit=floor.lower_limit - 0.5,",
     "subdivisions escaping their parent floor"),
    ("ulpin/ledger.py",
     ('        reserve_sequence(conn, parsed["parent_ulpin_14"], parsed["stratum"].value,\n'
      '                         parsed["level"], unit.unit_id, parsed["sequence"])'),
     "        pass",
     "provisional sequences colliding with allocated ones"),
    ("ulpin/ledger.py", "        if not parent_ulpin_14:", "        if False:",
     "units minted under a parcel nobody chose"),
    ("ulpin/lifecycle.py", "        if run is None:", "        if False:",
     "approval permitted with no validation recorded"),
    ("ulpin/lifecycle.py", "        if not run.approvable(unit.unit_id):", "        if False:",
     "approval permitted despite errors or unacknowledged warnings"),
    ("store.py", '    if row["severity"] == Severity.ERROR.value:', "    if False:",
     "errors acknowledged away instead of fixed"),
]


def suite_passes() -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", str(PKG / "tests"), "-q", "-x",
         "-W", "ignore::PendingDeprecationWarning"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    return r.returncode == 0


def main() -> int:
    if not suite_passes():
        print("FAIL  the unmutated suite is already red; fix that first")
        return 1
    print(f"baseline green, applying {len(MUTATIONS)} mutations\n")

    survivors = []
    for rel, find, replace, catches in MUTATIONS:
        path = PKG / rel
        original = path.read_text()
        if find not in original:
            print(f"  STALE   {rel}: pattern no longer present -- {catches}")
            survivors.append((rel, catches, "stale"))
            continue
        try:
            path.write_text(original.replace(find, replace, 1))
            caught = not suite_passes()
        finally:
            path.write_text(original)
        print(f"  {'caught ' if caught else 'SURVIVED'} {rel:<28} {catches}")
        if not caught:
            survivors.append((rel, catches, "survived"))

    print()
    if survivors:
        print(f"{len(survivors)} mutation(s) not caught. A rule whose deletion keeps the "
              "tests green is not being tested:")
        for rel, catches, why in survivors:
            print(f"  {why:<9} {rel} -- {catches}")
        return 1
    print(f"all {len(MUTATIONS)} mutations caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
