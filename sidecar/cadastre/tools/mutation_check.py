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
    # --- the project wizard's backend. A wrong setting here is not caught downstream,
    # it is inherited downstream by every unit the project will ever hold.
    ("api.py",
     "    if req.default_parapet_deduction_m:",
     "    if False:",
     "a parapet deduction accepted at creation, to surface only at derive"),
    ("api.py",
     "    horizontal_accuracy_m: float = Field(..., gt=0)",
     "    horizontal_accuracy_m: float = 0.20",
     "a source defaulting to survey-grade horizontal accuracy it never claimed"),
    ("api.py",
     "    vertical_accuracy_m: float = Field(..., gt=0)",
     "    vertical_accuracy_m: float = 0.25",
     "a source defaulting to survey-grade vertical accuracy it never claimed"),
    ("api.py",
     "    unknown = sorted({s.source_type for s in req.sources} - project.SOURCE_TYPES)",
     "    unknown = []",
     "a source type the form offers and the project silently drops"),
    ("project.py",
     "    if not gpkg.exists():",
     "    if False:",
     "a raster alone accepted as enough to start a project"),
    ("project.py",
     "    missing = [s.path for s in sources if not Path(s.path).exists()]",
     "    missing = []",
     "a project half-built around a file that was never there"),
    ("validate/rules/_util.py",
     "return max(a.lower_limit, b.lower_limit) < min(a.upper_limit, b.upper_limit) - tol_v",
     "return max(a.lower_limit, b.lower_limit) <= min(a.upper_limit, b.upper_limit) + tol_v",
     "touching floors counted as overlapping"),
    ("validate/rules/overlap.py",
     'if not parent.attributes.get("subdivided"):', "if False:",
     "unmodelled interiors reported as gaps"),
    ("validate/rules/overlap.py",
     "        if u.unit_type.is_easement:\n            continue\n", "",
     "two rights of way sharing a corridor called an overlap"),
    ("validate/rules/overlap.py",
     "            if other.unit_type is not u.unit_type:\n                continue\n", "",
     "a parcel reported as overlapping the building standing on it"),
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
    ("validate/rules/overlap.py",
     ("            if inter.area <= tolerance.negligible_area(tol_h):\n"
      "                continue\n"), "",
     "a shared wall between small units called a zero-area overlap"),
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
    ("project.py", "    if not overwrite:\n        held = _units_held(gpkg)\n",
     "    if False:\n        held = 0\n",
     "a project created over another, destroying its issued identifiers"),
    ("store.py", '    if row["severity"] == Severity.ERROR.value:', "    if False:",
     "errors acknowledged away instead of fixed"),

    # --- the P2 -> P4 import, and the payload the other blocks read -----------------
    ("ingest_gpkg.py",
     "    return shapely.wkb.loads(blob[8 + _ENVELOPE_BYTES[indicator]:])",
     "    return shapely.wkb.loads(blob)",
     "GeoPackage header fed to a plain WKB parser"),
    ("ingest_gpkg.py", "    indicator = (flags >> 1) & 0x07", "    indicator = 0",
     "envelope length assumed rather than read from the flags"),
    ("ingest_gpkg.py",
     "    if not parent_ulpin_14:\n        return None",
     '    if not parent_ulpin_14:\n        parent_ulpin_14 = "KA00X000000000"',
     "provisional identifiers minted under a placeholder parcel"),
    ("ingest_gpkg.py", "MAJORITY = 0.5", "MAJORITY = 0.0",
     "a building attached to a parcel holding a sliver of it"),
    ("ingest_gpkg.py",
     ('        return None, {"parcel_unresolved":\n'
      '                      f"names parcel {named_parcel}, which is not in this project"}'),
     "        pass",
     "a parcel id P2 got wrong replaced by a spatial guess"),
    ("ingest_gpkg.py",
     ("                created_by=CreatedBy.DERIVED,\n"
      "                lower_limit=None,\n"
      "                upper_limit=None,\n"
      "                recorded_from=now,\n"
      "                attributes=attrs,"),
     ("                created_by=CreatedBy.DERIVED,\n"
      "                lower_limit=settings.stratum_below_limit_m,\n"
      "                upper_limit=settings.stratum_above_limit_m,\n"
      "                recorded_from=now,\n"
      "                attributes=attrs,"),
     "buildings given the parcel's stratum instead of an unknown height"),
    ("ingest_gpkg.py",
     ("        existing = known.get((kind, local_id))\n"
      "        return (existing, True) if existing else (str(uuid.uuid4()), False)"),
     "        return str(uuid.uuid4()), False",
     "re-import minting a second identity for the same parcel"),
    ("store.py",
     ('    conn.executemany(\n'
      '        "UPDATE unit SET validation_state = ? WHERE unit_id = ?",\n'
      '        [(run.state_of(uid).value, uid) for uid in covered],\n'
      '    )'),
     "    pass",
     "validation results never reaching the units consumers read"),
    # --- the P4 -> P5/P6 seam: what a published record has to carry ----------------
    ("ingest_gpkg.py",
     ("                report.relationships.append(\n"
      "                    Relationship(uid, parcel_uid, RelType.INSIDE, now))\n"),
     "",
     "a published building with no parcel above it"),
    ("derive.py",
     '    parent = floor.attributes.get("parent_ulpin_14")\n    if not parent:\n        return False',
     '    parent = floor.attributes.get("parent_ulpin_14")\n    if not parent:\n        parent = "KA00X000000000"',
     "floor identifiers minted under a parcel nobody chose"),
    ("derive.py",
     "            if _identify(conn, floor, settings):\n                report.floors_identified += 1\n",
     "",
     "derived floors published as bare uuids"),
    ("derive.py",
     ("            save_relationship(conn, Relationship(\n"
      "                floor.unit_id, rebuilt.unit_id, RelType.INSIDE, datetime.now(UTC)))\n"),
     "",
     "a published floor with no building above it"),
    ("derive.py", "    level = abs(index)", "    level = 0",
     "every storey identified as the ground floor"),
    ("derive.py", "    if level > 99:", "    if False:",
     "a storey above the two-digit ceiling wrapping onto another floor's identifier"),
    ("store.py",
     "    except sqlite3.OperationalError as err:\n        raise ProjectIncomplete(\n            \"no `unit` table",
     "    except ZeroDivisionError as err:\n        raise ProjectIncomplete(\n            \"no `unit` table",
     "a GeoPackage that is not a project answering 500 instead of 422"),
    # --- the P3 -> P4 seam: FR-05, and what a human decided --------------------------
    ("suggestions.py",
     "\"SELECT * FROM ai_suggestion WHERE review_state IN ('accepted', 'edited') \"",
     ("\"SELECT * FROM ai_suggestion WHERE review_state IN "
      "('accepted', 'edited', 'pending', 'rejected') \""),
     "an AI outline becoming a unit with nobody's name on it"),
    ("suggestions.py",
     "    if row[\"review_state\"] == \"edited\":\n        return json.loads(row[\"edited_geometry\"])",
     "    if False:\n        return json.loads(row[\"edited_geometry\"])",
     "a reviewer's correction discarded for the outline the model drew"),
    ("suggestions.py",
     "    if raw[\"crs\"] != settings.project_crs:", "    if False:",
     "a suggestion in another CRS read as metres in the project grid"),
    ("suggestions.py", "    if errors:", "    if False:",
     "a suggestion the inbound contract does not describe imported anyway"),
    ("suggestions.py",
     "        if row is not None and row[0] != \"pending\":", "        if False:",
     "re-running the detector erasing a decision somebody made"),
    ("suggestions.py",
     "    if row[0] is not None:\n        raise AlreadyApplied(", "    if False:\n        raise AlreadyApplied(",
     "a suggestion re-decided after it already carries an identity"),
    ("suggestions.py",
     "        uid = row[\"unit_id\"] or str(uuid.uuid4())", "        uid = str(uuid.uuid4())",
     "re-applying minting a second building for the same suggestion"),
    ("suggestions.py", "        created_by=CreatedBy.AI,", "        created_by=CreatedBy.DERIVED,",
     "AI provenance lost, and CONFIDENCE_LOW silenced with it"),
    ("suggestions.py",
     "        resolved = by_raster.get(rid) or rid", "        resolved = rid",
     "a raster id stored where a source id belongs, so no tolerance can be derived"),
    ("suggestions.py",
     "    if ground is not None and roof is not None:", "    if ground is not None or roof is not None:",
     "half a height treated as a height"),
    ("detect.py",
     ("        mapped = already_mapped(conn, geom)\n"
      "        if mapped is not None:\n"
      "            report.already_mapped.append(mapped)\n"
      "            continue\n"), "",
     "a review queue filled with buildings the project already holds"),
    ("detect.py",
     ("        return process_ndsm_detection(ndsm, dsm, dem, raster_ids, crs=crs,\n"
      "                                      transform=transform)"),
     "        return process_ndsm_detection(ndsm, dsm, dem, raster_ids, crs=crs)",
     "detection geometry left in pixel indices, 276 km from its parcel"),
    ("detect.py",
     "    got = suggestions.receive(conn, fresh, settings)",
     "    got = suggestions.ReceiveReport(len(fresh), len(fresh))",
     "detector output reaching the queue without passing the contract gate"),
    ("detect.py",
     ("        seen = _rediscovery(conn, geom)\n"
      "        if seen is not None:"),
     ("        seen = _rediscovery(conn, geom)\n"
      "        if False:"),
     "pressing detect again re-asking a question somebody already settled"),
    ("detect.py",
     ("        if shared > MAJORITY * geom.area and shared > MAJORITY * other.area:\n"
      "            return row[\"suggestion_id\"]"),
     ("        if shared >= 0.0:\n"
      "            return row[\"suggestion_id\"]"),
     "a neighbouring building swallowed as a re-detection of its neighbour"),
    ("store.py",
     "    CHECK (review_state <> 'edited' OR edited_geometry IS NOT NULL),",
     "    CHECK (1 = 1),",
     "an edit falling back to the geometry it was correcting"),
    ("store.py",
     "    CHECK (review_state = 'pending' OR reviewed_by IS NOT NULL)",
     "    CHECK (1 = 1)",
     "a decision recorded with no author"),

    # --- the API reference, which drifted to 3 routes out of 15 once already ---------
    ("README.md", "#### `GET /cadastre/document`", "#### `GET /cadastre/documentt`",
     "a route the reference stops describing"),
    ("README.md", "Eighteen operations across seventeen paths",
     "Seventeen operations across seventeen paths",
     "a count in the reference that no longer matches the router"),
    ("store.py",
     ("    covered = (\n"
      "        validated_unit_ids\n"
      "        if validated_unit_ids is not None\n"
      '        else [r["unit_id"] for r in conn.execute("SELECT unit_id FROM unit")]\n'
      "    )"),
     '    covered = [r["unit_id"] for r in conn.execute("SELECT unit_id FROM unit")]',
     "a scoped run marking units it never looked at"),
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
