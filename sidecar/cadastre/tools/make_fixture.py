#!/usr/bin/env python3
"""Generate the demo fixture.

One parcel, one building, eight floors, three apartments, a water main and a walkway -
with defects deliberately planted so every severity path in the review UI is exercised,
not just the happy path.

Downstream teams build against the OUTPUT of this script. Regenerate with:

    python3 tools/make_fixture.py

Geometry is deliberately axis-aligned so overlap areas are exact arithmetic and the
expected findings can be asserted to the square metre.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PKG  = Path(__file__).resolve().parents[1]          # sidecar/cadastre
REPO = Path(__file__).resolve().parents[3]          # repo root
sys.path.insert(0, str(PKG.parent))   # sidecar/ on the path

from cadastre.ulpin.encode import Stratum, format_ulpin  # noqa: E402

NOW = "2026-08-29T09:00:00Z"
CRS = "EPSG:32643"          # UTM 43N - projected, metres
VDATUM = "EGM2008"
PARENT_A = "KA05B012345678"
PARENT_B = "KA05B012345679"

# Site origin, roughly Bengaluru in UTM 43N
E, N = 445000.0, 1434000.0

GROUND = 912.4
PLINTH = 0.6
PARAPET = 1.0
ROOF_OBSERVED = 935.0


def rect(x0: float, y0: float, x1: float, y1: float) -> dict:
    """Axis-aligned rectangle as a GeoJSON Polygon in the project CRS."""
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


SOURCES = [
    {"source_id": "SRC-001", "source_type": "parcel_map", "name": "Village cadastral sheet 41/3",
     "provider": "State Revenue Dept", "capture_date": "2019-11-02", "crs": CRS,
     "vertical_datum": VDATUM, "horizontal_accuracy_m": 0.30, "vertical_accuracy_m": 0.50,
     "processing_status": "ok"},
    {"source_id": "SRC-002", "source_type": "footprint", "name": "Drone photogrammetry run 2026-03",
     "provider": "Pilot survey", "capture_date": "2026-03-14", "crs": CRS,
     "vertical_datum": VDATUM, "horizontal_accuracy_m": 0.15, "vertical_accuracy_m": 0.25,
     "processing_status": "ok"},
    {"source_id": "SRC-003", "source_type": "dsm", "name": "DSM 0.25m", "provider": "Pilot survey",
     "capture_date": "2026-03-14", "crs": CRS, "vertical_datum": VDATUM,
     "horizontal_accuracy_m": 0.20, "vertical_accuracy_m": 0.30, "processing_status": "ok"},
    {"source_id": "SRC-004", "source_type": "dem", "name": "DEM 0.25m", "provider": "Pilot survey",
     "capture_date": "2026-03-14", "crs": CRS, "vertical_datum": VDATUM,
     "horizontal_accuracy_m": 0.20, "vertical_accuracy_m": 0.30, "processing_status": "ok"},
    {"source_id": "SRC-005", "source_type": "floorplan", "name": "Approved plan, 1st floor",
     "provider": "Municipal building permission", "capture_date": "2018-06-20", "crs": CRS,
     "vertical_datum": "local:FFL0", "horizontal_accuracy_m": 0.05, "vertical_accuracy_m": 0.05,
     "processing_status": "ok"},
    {"source_id": "SRC-006", "source_type": "utility_asbuilt", "name": "Water main as-built",
     "provider": "Water Board", "capture_date": "2011-01-30", "crs": CRS,
     "vertical_datum": VDATUM, "horizontal_accuracy_m": 0.50, "vertical_accuracy_m": 1.00,
     "processing_status": "ok"},
    # Deliberately incomplete - drives the PROVENANCE_MISSING finding.
    {"source_id": "SRC-007", "source_type": "footprint", "name": "Skywalk alignment sketch",
     "provider": "Unknown", "capture_date": "2022-08-01", "crs": CRS,
     "vertical_datum": VDATUM, "horizontal_accuracy_m": None, "vertical_accuracy_m": None,
     "processing_status": "accuracy_unknown"},
]

BLD = (E + 8, N + 6, E + 32, N + 24)          # 24 x 18 m, inside PCL-001

# base 913.0 -> top 936.5. Ground floor is deliberately 5.5 m (retail height).
FLOORS = [
    ("FLR-B01", -1, 909.4, 913.0),
    ("FLR-000",  0, 913.0, 918.5),   # 5.5 m  -> WARNING
    ("FLR-001",  1, 918.5, 921.5),
    ("FLR-002",  2, 921.5, 924.5),
    ("FLR-003",  3, 924.5, 927.5),
    ("FLR-004",  4, 927.5, 930.5),
    ("FLR-005",  5, 930.9, 933.5),   # 0.4 m gap under it -> ERROR
    ("FLR-006",  6, 933.5, 936.5),
]

# Three flats on FLR-001. The third starts 0.4 m inside the second -> ERROR.
APTS = [
    ("APT-101", 1, E + 8,    E + 16),
    ("APT-102", 2, E + 16,   E + 24),
    ("APT-103", 3, E + 23.6, E + 32),
]


def unit(uid, utype, status, footprint, lo, hi, sources, created_by="derived", **kw) -> dict:
    u = {
        "unit_id": uid, "unit_type": utype, "status": status,
        "representation": "prism", "crs": CRS, "vertical_datum": VDATUM,
        "footprint_2d": footprint, "lower_limit": lo, "upper_limit": hi,
        "source_ids": sources, "created_by": created_by,
        "validation_state": "unvalidated", "dispute_state": "undisputed",
        "recorded_from": NOW, "attributes": {},
    }
    u.update(kw)
    return u


units: list[dict] = []
rels: list[dict] = []


def relate(a: str, b: str, kind: str) -> None:
    rels.append({"from_unit_id": a, "to_unit_id": b, "rel_type": kind, "created_at": NOW})


# --- parcels: the only APPROVED units, so they carry frozen ULPINs -------------
for uid, parent, x0 in (("PCL-001", PARENT_A, E), ("PCL-002", PARENT_B, E + 40)):
    units.append(unit(
        uid, "land_parcel", "approved", rect(x0, N, x0 + 40, N + 30),
        GROUND - 30.0, GROUND + 150.0, ["SRC-001"], created_by="human",
        ulpin=format_ulpin(parent, 1, Stratum.SURFACE, 0, 0), ulpin_version="v1",
        validation_state="passed",
        attributes={"parent_ulpin_14": parent},
    ))

# --- building -----------------------------------------------------------------
units.append(unit(
    "BLD-001", "building", "needs_review", rect(*BLD), 909.4, 936.5,
    ["SRC-002", "SRC-003", "SRC-004"], created_by="ai",
    ulpin_provisional=format_ulpin(PARENT_A, 1, Stratum.SURFACE, 0, 1), ulpin_version="v1",
    confidence_score=0.87,
    model={"name": "yolov8s-seg-buildings", "version": "0.3.1", "run_at": NOW},
    attributes={"ground_level_m": GROUND, "roof_level_m": ROOF_OBSERVED,
                "plinth_offset_m": PLINTH, "parapet_deduction_m": PARAPET,
                "floor_count": 8},
))
relate("PCL-001", "BLD-001", "contains")
relate("BLD-001", "PCL-001", "inside")

# --- floors -------------------------------------------------------------------
for uid, idx, lo, hi in FLOORS:
    stratum, level = (Stratum.BELOW, abs(idx)) if idx < 0 else (Stratum.ABOVE, idx)
    units.append(unit(
        uid, "floor", "needs_review", rect(*BLD), lo, hi,
        ["SRC-002", "SRC-003", "SRC-004"],
        ulpin_provisional=format_ulpin(PARENT_A, 1, stratum, level, 0), ulpin_version="v1",
        confidence_score=0.72,
        attributes={"floor_index": idx, "floor_height_m": round(hi - lo, 2),
                    "subdivided": uid == "FLR-001"},
    ))
    relate("BLD-001", uid, "contains")
    relate(uid, "BLD-001", "inside")

# --- apartments on FLR-001 ----------------------------------------------------
_, _, F1_LO, F1_HI = FLOORS[2]
for uid, seq, x0, x1 in APTS:
    units.append(unit(
        uid, "apartment", "needs_review", rect(x0, N + 6, x1, N + 24), F1_LO, F1_HI,
        ["SRC-005"], created_by="human",
        ulpin_provisional=format_ulpin(PARENT_A, 1, Stratum.ABOVE, 1, seq), ulpin_version="v1",
        attributes={"floor_index": 1},
    ))
    relate("FLR-001", uid, "contains")
    relate(uid, "FLR-001", "inside")

# --- easements: these CROSS parcel boundaries, and that is correct -------------
units.append(unit(
    "UGF-001", "underground_feature", "needs_review",
    rect(E - 5, N + 14, E + 85, N + 16), 910.4, 911.9, ["SRC-006"], created_by="human",
    ulpin_provisional=format_ulpin(PARENT_A, 1, Stratum.BELOW, 0, 2), ulpin_version="v1",
    attributes={"easement": True, "utility_kind": "water", "corridor_width_m": 2.0},
))
units.append(unit(
    "ELV-001", "elevated_structure", "needs_review",
    rect(E + 30, N + 26, E + 70, N + 29), 920.0, 923.0, ["SRC-007"], created_by="human",
    ulpin_provisional=format_ulpin(PARENT_A, 1, Stratum.ABOVE, 2, 1), ulpin_version="v1",
    attributes={"easement": True, "utility_kind": "walkway"},
))

# --- what a correct validator must produce ------------------------------------
OVERLAP_M2 = round((E + 24 - (E + 23.6)) * 18, 2)
GAP_M = round(FLOORS[6][2] - FLOORS[5][3], 2)

expected = [
    {"rule_id": "OVERLAP_SIBLING", "severity": "error", "unit_id": "APT-102",
     "related_unit_ids": ["APT-103"], "measured_value": OVERLAP_M2,
     "note": "0.4 m penetration over an 18 m shared edge. Tolerance from SRC-005 "
             "(0.05 m) is 0.07 m, so this is far outside measurement error."},
    {"rule_id": "FLOOR_SEQUENCE", "severity": "error", "unit_id": "FLR-005",
     "related_unit_ids": ["FLR-004"], "measured_value": GAP_M,
     "note": "FLR-004 ends at 930.5 but FLR-005 starts at 930.9. Floors must be contiguous."},
    {"rule_id": "UTILITY_CROSSES_BUILDING", "severity": "error", "unit_id": "UGF-001",
     "related_unit_ids": ["FLR-B01"], "measured_value": None,
     "note": "Water main at 910.4-911.9 runs through the basement (909.4-913.0). "
             "Crossing a parcel is fine; crossing an ownership volume is not."},
    {"rule_id": "FLOOR_HEIGHT_IMPLAUSIBLE", "severity": "warning", "unit_id": "FLR-000",
     "related_unit_ids": [], "measured_value": 5.5,
     "note": "Outside the 2.4-5.0 m band. Plausible for retail, so a warning a reviewer "
             "can acknowledge - not an error that blocks approval."},
    {"rule_id": "PROVENANCE_MISSING", "severity": "info", "unit_id": "ELV-001",
     "related_unit_ids": [], "measured_value": None,
     "note": "SRC-007 has null accuracy, so no tolerance can be derived for this unit."},
]

must_not_fire = [
    {"rule_id": "ESCAPES_PARENT", "unit_id": "UGF-001",
     "note": "NEGATIVE TEST. UGF-001 spans PCL-001 and PCL-002 and extends beyond both. "
             "It is an easement, not an ownership volume, so leaving the parcel is "
             "expected. A validator that flags this has implemented containment as "
             "unconditional and is wrong."},
    {"rule_id": "GAP_SIBLING", "unit_id": "FLR-001",
     "note": "NEGATIVE TEST. The three flats tile FLR-001 exactly, so there is no gap. "
             "Other floors have subdivided=false and must not be gap-checked at all."},
]

bundle = {
    "$comment": "Generated by tools/make_fixture.py - edit the generator, not this file.",
    "project": {
        "project_crs": CRS, "vertical_datum": VDATUM,
        "stratum_below_limit_m": -30.0, "stratum_above_limit_m": 150.0,
        "default_plinth_offset_m": PLINTH, "default_parapet_deduction_m": PARAPET,
        "ulpin_version": "v1", "ruleset_version": "r1",
        "min_floor_height_m": 2.4, "max_floor_height_m": 5.0,
        "confidence_warn_below": 0.6, "tolerance_k": 1.0,
    },
    "sources": SOURCES,
    "units": units,
    "relationships": rels,
    "expected_findings": expected,
    "must_not_fire": must_not_fire,
}

out = REPO / "contracts/fixtures/demo-parcel.json"
out.write_text(json.dumps(bundle, indent=2) + "\n")
print(f"wrote {out.relative_to(REPO)}")
print(f"  units {len(units)}  relationships {len(rels)}  sources {len(SOURCES)}")
print(f"  expected findings {len(expected)}  negative tests {len(must_not_fire)}")
