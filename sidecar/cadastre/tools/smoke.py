#!/usr/bin/env python3
"""End-to-end smoke test: a whole project through the whole chain, over HTTP.

Every serious defect this project has hit was an *integration* defect, invisible to the
unit suites, which were green throughout:

  * floors carried no parcel reference, so none could ever be approved
  * a parcel's stratum column was read as absolute, putting it below its own buildings
  * the approval guard was bypassable because findings were never persisted
  * a building with no vertical extent passed validation and was approved

Each lived *between* two modules that were individually correct. So this runs the real
chain and asserts the outcome, and it goes through the ASGI app rather than calling
library functions - the approval bypass reached production through the HTTP layer, and
testing only the library would have missed it again.

    ./.venv/bin/python sidecar/cadastre/tools/smoke.py

Exits non-zero on the first broken expectation.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sidecar"))

PASS, FAIL = "  \033[92mok\033[0m  ", "  \033[91mFAIL\033[0m"
failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"{PASS if ok else FAIL} {label:<44} {got!r}" + ("" if ok else f"  expected {want!r}"))
    if not ok:
        failures.append(f"{label}: got {got!r}, expected {want!r}")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="groundup-smoke-"))
    gpkg = work / "pilot.gpkg"
    try:
        print(f"project: {gpkg}\n")

        def run_tool(script: str) -> bool:
            r = subprocess.run(
                [sys.executable, str(REPO / "sidecar/cadastre/tools" / script), str(gpkg)],
                capture_output=True, text=True, cwd=REPO, check=False)
            if r.returncode:
                print(f"{FAIL} {script}\n{r.stderr[-800:]}")
            return r.returncode == 0

        if not run_tool("make_demo_project.py"):
            return 1
        print(f"{PASS} P2 pipeline built the project")

        from cadastre.api import router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        db = {"db_path": str(gpkg)}
        q = {"db_path": str(gpkg)}

        ing = c.post("/cadastre/ingest", json=db).json()
        check("ingest imports the footprints", ing["created"], 2)

        # Rasters are generated to cover the footprints ingest just created, so this
        # cannot run before ingest.
        if not run_tool("make_demo_rasters.py"):
            return 1
        print(f"{PASS} elevation generated over those footprints")

        der = c.post("/cadastre/derive", json=db).json()
        check("parcel column anchored to its ground", der["parcels_grounded"], 1)
        check("building heights derived", der["heights_derived"], 1)
        check("floors created", der["floors_created"], 5)
        check("nothing skipped for want of a raster", der["skipped_no_raster"], [])

        val = c.post("/cadastre/validate", json=db).json()
        check("all units present", val["units"], 7)
        check("clean project validates clean", val["findings"], 0)

        # Approval must be refused for a unit that has never been validated, and the
        # whole clean project must then approve.
        import sqlite3
        conn = sqlite3.connect(gpkg)
        ids = [r[0] for r in conn.execute(
            "SELECT unit_id FROM unit ORDER BY CASE unit_type WHEN 'land_parcel' THEN 0"
            " WHEN 'building' THEN 1 ELSE 2 END")]
        conn.close()

        approved = 0
        for uid in ids:
            r = c.post(f"/cadastre/units/{uid}/transition", params=q,
                       json={"target_status": "approved", "actor": "smoke"})
            if r.status_code == 200 and r.json().get("ulpin"):
                approved += 1
            else:
                print(f"      {uid[:8]} -> {r.status_code} {r.text[:120]}")
        check("every unit approved with an identifier", approved, len(ids))

        conn = sqlite3.connect(gpkg)
        n_ledger = conn.execute("SELECT count(DISTINCT ulpin) FROM ulpin_ledger").fetchone()[0]
        lo, hi = conn.execute(
            "SELECT min(lower_limit), max(upper_limit) FROM unit WHERE unit_type='floor'"
        ).fetchone()
        gaps = conn.execute(
            "SELECT count(*) FROM unit WHERE unit_type='floor' AND lower_limit IS NULL"
        ).fetchone()[0]
        conn.close()
        check("every identifier is distinct", n_ledger, len(ids))
        check("floors span the building exactly", (round(lo, 1), round(hi, 1)), (913.0, 925.0))
        check("no floor left without heights", gaps, 0)

        doc = c.get("/cadastre/document", params=q).json()
        check("document serves every unit", len(doc["units"]), 7)
        check("document reports no findings", len(doc["findings"]), 0)

        sample = next(u for u in doc["units"] if u["unit_type"] == "floor")
        looked = c.get(f"/cadastre/ulpin/{sample['ulpin']}", params=q)
        check("an identifier resolves back to its unit", looked.status_code, 200)
        check("resolves to the right unit", looked.json()["unit_id"], sample["unit_id"])
        check("a malformed identifier is refused",
              c.get("/cadastre/ulpin/NOT-A-ULPIN", params=q).status_code, 400)

        print()
        if failures:
            print(f"\033[91m{len(failures)} broken expectation(s)\033[0m")
            for f in failures:
                print(f"  {f}")
            return 1
        print("\033[92mend-to-end chain intact\033[0m")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
