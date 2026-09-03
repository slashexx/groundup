"""The outbound payload, and the application that serves it.

Two things are asserted here that no other test could catch:

* the document validates against `contracts/outbound/*.schema.json`, which is what P5
  and P6 generate their types from - a payload that drifts from the schema is a defect
  delivered to a teammate;
* the app actually answers. `api.router` is an `APIRouter`; uvicorn starts happily with
  one as its target and then returns 500 on every route. That failure is invisible to
  every test that builds its own `FastAPI()` first, which is all of them until now.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from cadastre import export, store, validate
from cadastre.app import app
from cadastre.models import ValidationState
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

REPO = pathlib.Path(__file__).resolve().parents[3]
UNIT_SCHEMA = Draft202012Validator(
    json.loads((REPO / "contracts/outbound/unit.schema.json").read_text()))
FINDING_SCHEMA = Draft202012Validator(
    json.loads((REPO / "contracts/outbound/finding.schema.json").read_text()))


@pytest.fixture
def project(tmp_path, bundle):
    """The fixture project, persisted the way the API sees it."""
    db = tmp_path / "pilot.gpkg"
    conn = store.connect(str(db))
    store.init_schema(conn)
    conn.executescript(
        "CREATE TABLE source (source_id TEXT PRIMARY KEY, horizontal_accuracy_m REAL,"
        " vertical_accuracy_m REAL);"
        "CREATE TABLE project_settings (project_crs TEXT, vertical_datum TEXT,"
        " stratum_below_limit_m REAL, stratum_above_limit_m REAL,"
        " default_plinth_offset_m REAL, default_parapet_deduction_m REAL,"
        " ulpin_version TEXT, ruleset_version TEXT);"
    )
    raw = bundle["raw"]
    for s in raw["sources"]:
        conn.execute("INSERT INTO source VALUES (?,?,?)",
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
    return str(db)


# --- the payload ---------------------------------------------------------------------

def test_every_exported_unit_satisfies_the_outbound_schema(bundle):
    doc = export.document(bundle["settings"], bundle["units"], bundle["relationships"])
    assert len(doc["units"]) == 16
    for u in doc["units"]:
        errors = [e.message for e in UNIT_SCHEMA.iter_errors(u)]
        assert not errors, f"{u['unit_id']}: {errors}"


def test_every_exported_finding_satisfies_the_outbound_schema(bundle, result):
    doc = export.document(bundle["settings"], bundle["units"],
                          bundle["relationships"], result.findings)
    assert len(doc["findings"]) == 5
    for f in doc["findings"]:
        errors = [e.message for e in FINDING_SCHEMA.iter_errors(f)]
        assert not errors, f"{f['finding_id']}: {errors}"


def test_findings_are_published_under_both_keys(bundle, result):
    """P5's adapter was written against the fixture, which calls them expectations."""
    doc = export.document(bundle["settings"], bundle["units"],
                          bundle["relationships"], result.findings)
    assert doc["findings"] == doc["expected_findings"]


def test_the_document_carries_what_the_viewer_derives_ground_from(bundle):
    """P5 shifts display heights by parcel.lower_limit - stratum_below_limit_m."""
    doc = export.document(bundle["settings"], bundle["units"], bundle["relationships"])
    assert doc["project"]["stratum_below_limit_m"] == -30.0
    parcels = [u for u in doc["units"] if u["unit_type"] == "land_parcel"]
    assert parcels and all(u["lower_limit"] is not None for u in parcels)


def test_an_unknown_height_is_exported_as_null_not_dropped(bundle):
    """FR-03 has to survive serialisation, or the viewer cannot tell unknown from zero.

    Built here rather than taken from the fixture because every unit in
    `demo-parcel.json` currently has a height - so the committed fixture never exercises
    the unknown-height path that P5 renders as a grey marker slab, and every unit
    imported from P2 takes exactly that path. Recorded in `08-open-questions.md`.
    """
    import dataclasses
    unknown = dataclasses.replace(bundle["units"][0], lower_limit=None, upper_limit=None)
    doc = export.document(bundle["settings"], [unknown], [])
    u = doc["units"][0]
    assert "lower_limit" in u and u["lower_limit"] is None
    assert "upper_limit" in u and u["upper_limit"] is None
    assert not [e.message for e in UNIT_SCHEMA.iter_errors(u)]


# --- validation state is written back ------------------------------------------------

def test_a_run_writes_each_units_validation_state_back(project, bundle):
    """The column is contract surface: it is what P5 colours by and P1 sorts by."""
    conn = store.connect(project)
    units, rels, sources, settings = store.load_project(conn)
    run = validate.run(units, rels, sources, settings)
    store.save_run(conn, run, [u.unit_id for u in units])

    states = dict(conn.execute("SELECT unit_id, validation_state FROM unit"))
    assert states["APT-102"] == ValidationState.FAILED.value        # OVERLAP_SIBLING
    assert states["FLR-000"] == ValidationState.PASSED_WITH_WARNINGS.value
    assert states["FLR-002"] == ValidationState.PASSED.value
    assert ValidationState.UNVALIDATED.value not in states.values()
    conn.close()


def test_a_scoped_run_does_not_mark_units_it_never_looked_at(project):
    """Passing a unit on the strength of a run that skipped it is the same error class
    as approving one with no run at all."""
    conn = store.connect(project)
    units, rels, sources, settings = store.load_project(conn)
    run = validate.run(units, rels, sources, settings)
    store.save_run(conn, run, ["FLR-002"])

    states = dict(conn.execute("SELECT unit_id, validation_state FROM unit"))
    assert states["FLR-002"] == ValidationState.PASSED.value
    assert states["APT-102"] == ValidationState.UNVALIDATED.value
    conn.close()


# --- the application ------------------------------------------------------------------

def test_the_app_serves_the_router(project):
    """`uvicorn cadastre.api:router` returns 500 here. `cadastre.app:app` returns 200."""
    c = TestClient(app)
    assert c.get("/cadastre/health").json() == {"status": "ok", "block": "cadastre"}

    index = c.get("/").json()
    assert index["block"] == "P4 · cadastre"
    # The index enumerates the router, not app.routes — recent FastAPI keeps an included
    # router as one opaque entry and filtering app.routes yields nothing at all.
    assert "/cadastre/document" in index["routes"]
    assert "/cadastre/ingest" in index["routes"]


def test_the_document_endpoint_serves_a_validated_project(project):
    c = TestClient(app)
    assert c.post("/cadastre/validate", json={"db_path": project}).status_code == 200

    doc = c.get("/cadastre/document", params={"db_path": project}).json()
    assert len(doc["units"]) == 16
    assert len(doc["findings"]) == 5
    assert doc["project"]["project_crs"] == "EPSG:32643"
    # The state the run computed reaches the payload, not the unvalidated default.
    by_id = {u["unit_id"]: u for u in doc["units"]}
    assert by_id["APT-102"]["validation_state"] == "failed"


def test_the_document_endpoint_refuses_an_unbuilt_project(tmp_path):
    """An empty GeoPackage is a real condition, not a reason to invent a project CRS."""
    db = tmp_path / "empty.gpkg"
    store.init_schema(store.connect(str(db)))
    r = TestClient(app).get("/cadastre/document", params={"db_path": str(db)})
    assert r.status_code == 422
    assert "source" in r.json()["detail"]


def test_cors_allows_the_desktop_shell_and_refuses_a_stranger():
    """The sidecar answers on localhost while a browser is open on the same machine."""
    c = TestClient(app)
    allowed = c.get("/cadastre/health", headers={"Origin": "http://localhost:1420"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:1420"
    stranger = c.get("/cadastre/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in stranger.headers
