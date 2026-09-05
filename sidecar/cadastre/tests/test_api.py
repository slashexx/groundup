"""End-to-end through the HTTP surface, against a real GeoPackage on disk.

The approval bypass reached production through the API rather than through the library:
`lifecycle.transition` was called without a validation run, and the guard treated that as
permission. So the guard is asserted here too, at the layer that actually failed.
"""

from __future__ import annotations

import pytest
from cadastre import store
from cadastre.api import router
from cadastre.models import Status
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, bundle):
    db = tmp_path / "pilot.gpkg"
    conn = store.connect(str(db))
    store.init_schema(conn)
    conn.executescript(
        "CREATE TABLE source (source_id TEXT PRIMARY KEY, source_type TEXT, name TEXT,"
        " provider TEXT, capture_date TEXT, crs TEXT, vertical_datum TEXT,"
        " horizontal_accuracy_m REAL, vertical_accuracy_m REAL, coverage_wkt TEXT,"
        " processing_status TEXT);"
        "CREATE TABLE project_settings (project_crs TEXT, vertical_datum TEXT,"
        " stratum_below_limit_m REAL, stratum_above_limit_m REAL,"
        " default_plinth_offset_m REAL, default_parapet_deduction_m REAL,"
        " ulpin_version TEXT, ruleset_version TEXT);"
    )
    raw = bundle["raw"]
    for s in raw["sources"]:
        conn.execute("INSERT INTO source (source_id, horizontal_accuracy_m, vertical_accuracy_m)"
                     " VALUES (?,?,?)",
                     (s["source_id"], s["horizontal_accuracy_m"], s["vertical_accuracy_m"]))
    p = raw["project"]
    conn.execute("INSERT INTO project_settings VALUES (?,?,?,?,?,?,?,?)",
                 (p["project_crs"], p["vertical_datum"], p["stratum_below_limit_m"],
                  p["stratum_above_limit_m"], p["default_plinth_offset_m"],
                  p["default_parapet_deduction_m"], p["ulpin_version"], p["ruleset_version"]))
    for u in bundle["units"]:
        store.save_unit(conn, u)
    for r in bundle["relationships"]:
        store.save_relationship(conn, r)
    conn.commit()
    conn.close()

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    c.db = str(db)
    return c


def test_validation_endpoint_persists_the_fixture_findings(client):
    r = client.post("/cadastre/validate", json={"db_path": client.db})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["units"] == 16
    assert body["by_severity"] == {"error": 3, "warning": 1, "info": 1}

    latest = client.get("/cadastre/runs/latest", params={"db_path": client.db}).json()
    assert latest["run_id"] == body["run_id"]
    assert len(latest["findings"]) == 5


def test_approval_is_refused_before_any_validation(client):
    r = client.post("/cadastre/units/APT-102/transition",
                    json={"target_status": "approved", "actor": "anyone"},
                    params={"db_path": client.db})
    assert r.status_code == 400
    assert "no validation run" in r.json()["detail"]


def test_a_unit_with_errors_cannot_be_approved_through_the_api(client):
    client.post("/cadastre/validate", json={"db_path": client.db})
    r = client.post("/cadastre/units/APT-102/transition",
                    json={"target_status": "approved", "actor": "reviewer"},
                    params={"db_path": client.db})
    assert r.status_code == 400
    assert "OVERLAP_SIBLING" in r.json()["detail"]


def test_errors_cannot_be_acknowledged_away(client):
    """A reviewer may accept a warning. An error must be fixed and revalidated."""
    client.post("/cadastre/validate", json={"db_path": client.db})
    findings = client.get("/cadastre/runs/latest", params={"db_path": client.db}).json()["findings"]
    err = next(f for f in findings if f["severity"] == "error")
    r = client.post(f"/cadastre/findings/{err['finding_id']}/acknowledge",
                    json={"actor": "reviewer"}, params={"db_path": client.db})
    assert r.status_code == 409


def test_a_clean_unit_approves_and_the_identifier_resolves(client):
    client.post("/cadastre/validate", json={"db_path": client.db})
    r = client.post("/cadastre/units/FLR-002/transition",
                    json={"target_status": "approved", "actor": "reviewer"},
                    params={"db_path": client.db})
    assert r.status_code == 200, r.text
    ulpin = r.json()["ulpin"]
    assert r.json()["status"] == Status.APPROVED.value and ulpin

    looked_up = client.get(f"/cadastre/ulpin/{ulpin}", params={"db_path": client.db})
    assert looked_up.status_code == 200
    assert looked_up.json()["unit_id"] == "FLR-002"


def test_a_malformed_identifier_is_rejected_before_any_lookup(client):
    assert client.get("/cadastre/ulpin/NOT-A-ULPIN",
                      params={"db_path": client.db}).status_code == 400


# --- the reference in README.md ------------------------------------------------------
#
# §4.1 documented three routes out of fifteen for most of the project's life, and nothing
# said so. Documentation is the weakest enforcement there is, so this is the enforcement.

def test_the_api_reference_documents_every_route():
    """Every operation the router serves has a heading in the README, and vice versa.

    Both directions matter. A route nobody documented is the failure this caught; a
    heading for a route that no longer exists is the one that wastes a consumer's
    afternoon.
    """
    import pathlib
    import re

    readme = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text()
    section = readme.split("### 4.1 REST API Reference")[1].split("### 4.2 ")[0]

    served = {
        f"{method} {route.path}"
        for route in router.routes
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
    }
    documented = set(re.findall(r"^#### `([A-Z]+ /cadastre[^`]*)`", section, re.MULTILINE))

    assert served, "the router serves nothing; this test would pass vacuously"
    assert served - documented == set(), \
        f"undocumented routes: {sorted(served - documented)}"
    assert documented - served == set(), \
        f"documented routes that do not exist: {sorted(documented - served)}"


def test_the_api_reference_states_the_route_count_correctly():
    """A count in prose is a fact, and facts drift. This one is load-bearing: it is the
    first thing a reader checks the page against."""
    import pathlib
    import re

    readme = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text()
    served = {(m, r.path) for r in router.routes
              for m in getattr(r, "methods", set()) - {"HEAD", "OPTIONS"}}
    words = {14: "Fourteen", 15: "Fifteen", 16: "Sixteen", 17: "Seventeen",
             18: "Eighteen", 19: "Nineteen", 20: "Twenty"}
    stated = re.search(r"(\w+) operations across (\w+) paths", readme)

    assert stated, "the reference no longer states how many routes it covers"
    assert stated.group(1) == words[len(served)], (
        f"{len(served)} operations are served, the reference says {stated.group(1)}")
    assert stated.group(2) == words[len({p for _, p in served})].lower()
