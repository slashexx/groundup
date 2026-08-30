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
