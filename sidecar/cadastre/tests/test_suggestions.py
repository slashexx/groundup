"""The P3 -> P4 seam, and the human standing in it.

FR-05 is the requirement under test: an AI outline never becomes a unit without a person
saying so. Most of what follows asserts a *refusal*, because that is what the requirement
actually is - and two of these assert silence, which is the other half of a rule that is
worth anything.

Geometry is axis-aligned and metric so every expected value is arithmetic: a 20 x 20 m
footprint inside a 100 x 100 m parcel is 400 m2 of 10000, and the roof at 927.4 m over
ground at 912.4 m with a 0.6 m plinth gives a unit spanning exactly 913.0 -> 927.4.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

import pytest
import shapely.geometry
from cadastre import store, suggestions, validate
from cadastre.models import (
    Accuracy,
    CreatedBy,
    ProjectSettings,
    Relationship,
    RelType,
    Representation,
    Status,
    Unit,
    UnitType,
)

SETTINGS = ProjectSettings(
    project_crs="EPSG:32643", vertical_datum="EGM2008",
    stratum_below_limit_m=-30.0, stratum_above_limit_m=150.0,
    default_plinth_offset_m=0.6, default_parapet_deduction_m=0.0,
    ulpin_version="v1", ruleset_version="r1",
)

E, N = 445000.0, 1434000.0
PARENT = "KA05B012345678"
PARCEL = shapely.geometry.box(E, N, E + 100, N + 100)
INSIDE = shapely.geometry.box(E + 20, N + 20, E + 40, N + 40)      # 400 m2, well inside
ELSEWHERE = shapely.geometry.box(E + 5000, N + 5000, E + 5020, N + 5020)
GROUND, ROOF = 912.4, 927.4


def suggestion(geom=INSIDE, *, confidence=0.88, crs="EPSG:32643",
               ground=GROUND, roof=ROOF, floors=5, **overrides) -> dict:
    """One contract-shaped suggestion, as P3's SuggestionBuilder emits them."""
    attributes = {}
    if floors is not None:
        attributes |= {"floor_count": floors, "floor_count_method": "ndsm_division"}
    if ground is not None:
        attributes["ground_level_m"] = ground
    if roof is not None:
        attributes["roof_level_m"] = roof
    raw = {
        "suggestion_id": str(uuid.uuid4()),
        "kind": "building_outline",
        "geometry": shapely.geometry.mapping(geom),
        "crs": crs,
        "source_raster_ids": ["RST-DSM", "RST-DEM"],
        "confidence": confidence,
        "model": {"name": "yolov8s-seg-buildings", "version": "1.0.0",
                  "run_at": "2026-09-04T12:00:00+00:00"},
        "attributes": attributes,
        "review": {"state": "pending"},
    }
    return raw | overrides


@pytest.fixture
def project(tmp_path):
    """A project with one parcel already imported, as ingest leaves it."""
    conn = store.connect(str(tmp_path / "p.gpkg"))
    store.init_schema(conn)
    store.save_unit(conn, Unit(
        unit_id="PCL-1", unit_type=UnitType.LAND_PARCEL, status=Status.NEEDS_REVIEW,
        crs="EPSG:32643", vertical_datum="EGM2008",
        footprint_2d=shapely.geometry.mapping(PARCEL), source_ids=["src-parcels"],
        created_by=CreatedBy.DERIVED, representation=Representation.PRISM,
        attributes={"parent_ulpin_14": PARENT}))
    conn.commit()
    return conn


def one_unit(conn) -> Unit:
    rows = conn.execute("SELECT unit_id FROM unit WHERE unit_type = 'building'").fetchall()
    assert len(rows) == 1, f"expected exactly one building, got {len(rows)}"
    return store.get_unit(conn, rows[0]["unit_id"])


# --- the contract, at the door -------------------------------------------------------

def test_a_suggestion_missing_a_required_field_is_refused(project):
    bad = suggestion()
    del bad["confidence"]
    with pytest.raises(suggestions.ContractViolation, match="confidence"):
        suggestions.receive(project, [bad], SETTINGS)


def test_an_unknown_key_is_refused(project):
    """The schema sets additionalProperties: false, so a field we do not model is a
    contract change and not a courtesy to pass through."""
    with pytest.raises(suggestions.ContractViolation):
        suggestions.receive(project, [suggestion(height_m=15.0)], SETTINGS)


def test_a_batch_with_one_bad_entry_stores_none_of_it(project):
    """All or nothing. A half-imported batch from an upstream block is the kind of state
    nobody thinks to look for."""
    good, bad = suggestion(), suggestion()
    del bad["model"]
    with pytest.raises(suggestions.ContractViolation):
        suggestions.receive(project, [good, bad], SETTINGS)
    assert project.execute("SELECT count(*) FROM ai_suggestion").fetchone()[0] == 0


def test_a_suggestion_in_another_crs_is_refused(project):
    """Suggestion geometry is in the project CRS by contract, and P4 does not reproject.

    The numbers in a WGS84 polygon are perfectly plausible metres, so nothing downstream
    would notice; the building would simply be somewhere off the coast of Africa.
    """
    with pytest.raises(suggestions.ContractViolation, match="EPSG:4326"):
        suggestions.receive(project, [suggestion(crs="EPSG:4326")], SETTINGS)


# --- FR-05: no unit without a human --------------------------------------------------

def test_a_pending_suggestion_never_becomes_a_unit(project):
    suggestions.receive(project, [suggestion()], SETTINGS)
    report = suggestions.apply(project, SETTINGS)
    assert report.units == 0
    assert project.execute("SELECT count(*) FROM unit WHERE unit_type='building'"
                           ).fetchone()[0] == 0


def test_a_rejected_suggestion_never_becomes_a_unit(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "rejected", "bibisha")
    assert suggestions.apply(project, SETTINGS).units == 0


def test_an_accepted_suggestion_becomes_a_building(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    report = suggestions.apply(project, SETTINGS)

    assert (report.units, report.created, report.with_heights) == (1, 1, 1)
    u = one_unit(project)
    assert u.unit_type is UnitType.BUILDING
    assert u.status is Status.NEEDS_REVIEW          # accepted the outline, not the record
    assert u.attributes["suggestion_id"] == raw["suggestion_id"]


def test_applying_one_pending_suggestion_by_name_is_refused_out_loud(project):
    """`apply()` skips silently, which is right for a batch. Asked about one suggestion
    the caller believes is ready, silence would be the wrong answer."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    with pytest.raises(suggestions.NotReviewed, match="FR-05"):
        suggestions.apply_one(project, raw["suggestion_id"], SETTINGS)


def test_a_review_must_name_someone(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    with pytest.raises(ValueError, match="name"):
        suggestions.review(project, raw["suggestion_id"], "accepted", "")


def test_the_database_refuses_an_unsigned_decision(project):
    """The guard survives a caller that bypasses `review()` - which is the only kind of
    caller worth guarding against."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    with pytest.raises(sqlite3.IntegrityError):
        project.execute("UPDATE ai_suggestion SET review_state = 'accepted'")


# --- the reviewer's correction is the one that counts --------------------------------

def test_an_edited_suggestion_uses_the_reviewers_geometry_not_the_models(project):
    """The contract says P4 uses `edited_geometry`, not `geometry`. Reading the model's
    original outline here would discard the single correction a human actually made."""
    corrected = shapely.geometry.box(E + 20, N + 20, E + 30, N + 30)     # 100 m2, not 400
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "edited", "bibisha",
                       edited_geometry=shapely.geometry.mapping(corrected))
    suggestions.apply(project, SETTINGS)

    assert shapely.geometry.shape(one_unit(project).footprint_2d).area == 100.0


def test_an_edit_without_a_geometry_is_refused(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    with pytest.raises(ValueError, match="corrected geometry"):
        suggestions.review(project, raw["suggestion_id"], "edited", "bibisha")


def test_the_database_refuses_an_edit_with_no_corrected_geometry(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    with pytest.raises(sqlite3.IntegrityError):
        project.execute(
            "UPDATE ai_suggestion SET review_state = 'edited', reviewed_by = 'x'")


# --- provenance, which is what makes the AI unit different ---------------------------

def test_an_ai_building_carries_its_model_and_confidence(project):
    raw = suggestion(confidence=0.88)
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    u = one_unit(project)
    assert u.created_by is CreatedBy.AI
    assert u.confidence_score == 0.88
    assert (u.model.name, u.model.version) == ("yolov8s-seg-buildings", "1.0.0")


def test_a_low_confidence_ai_building_raises_confidence_low(project):
    """CONFIDENCE_LOW has been written since the first validation pass and could never
    fire: it keys on `created_by is AI` and no AI unit existed until this seam."""
    raw = suggestion(confidence=0.41)          # below the 0.6 default threshold
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    result = _validate(project)
    low = [f for f in result.findings if f.rule_id.value == "CONFIDENCE_LOW"]
    assert len(low) == 1
    assert low[0].measured_value == 0.41 and low[0].tolerance == 0.6


def test_a_confident_ai_building_does_not_raise_it(project):
    """The silence. A rule that fires on every AI unit would train reviewers to click
    through the one that matters."""
    raw = suggestion(confidence=0.88)
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    assert one_unit(project).created_by is CreatedBy.AI          # the rule *can* fire
    assert not [f for f in _validate(project).findings
                if f.rule_id.value == "CONFIDENCE_LOW"]


# --- heights: measured or absent, never in between -----------------------------------

def test_heights_follow_the_same_rule_as_a_raster_derived_building(project):
    """`extrude.building.build` puts the base at ground plus the plinth and the top at
    the roof level. A building the model found must mean the same thing."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    u = one_unit(project)
    assert u.lower_limit == pytest.approx(GROUND + 0.6)      # 913.0
    assert u.upper_limit == pytest.approx(ROOF)              # 927.4
    assert u.attributes["floor_count"] == 5


def test_a_suggestion_with_only_one_level_gets_no_height_at_all(project):
    """One level without the other is not half a height. FR-03: absent stays absent."""
    raw = suggestion(roof=None)
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    report = suggestions.apply(project, SETTINGS)

    u = one_unit(project)
    assert (u.lower_limit, u.upper_limit) == (None, None)
    assert u.attributes["heights_unavailable"]
    assert report.with_heights == 0
    # ...and it surfaces in the queue rather than passing quietly.
    assert any(f.rule_id.value == "HEIGHTS_UNAVAILABLE" for f in _validate(project).findings)


def test_raster_ids_are_translated_into_the_source_they_belong_to(project):
    """P3 names rasters; `Unit.source_ids` names sources, which is where accuracy lives.

    Storing a raster id in that column gives a unit whose provenance resolves to nothing,
    so every comparison involving it falls back to a default tolerance instead of one
    derived from what the data is worth - reported as PROVENANCE_MISSING, which is the
    right complaint about the wrong cause. Found by running the full chain and reading
    the findings.
    """
    project.executescript(
        "CREATE TABLE raster (raster_id TEXT PRIMARY KEY, kind TEXT, path TEXT,"
        " crs TEXT, vertical_datum TEXT, resolution_m REAL, source_id TEXT);")
    project.execute("INSERT INTO raster VALUES ('RST-DSM','DSM','','','',0.5,'SRC-ELEV')")
    project.execute("INSERT INTO raster VALUES ('RST-DEM','DEM','','','',0.5,'SRC-ELEV')")
    project.commit()

    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    u = one_unit(project)
    assert u.source_ids == ["SRC-ELEV"]          # one registry entry, not two raster ids
    # ...and which surfaces it came from is not lost, only moved.
    assert u.attributes["source_raster_ids"] == ["RST-DSM", "RST-DEM"]


def test_a_raster_with_no_registry_entry_is_carried_through_not_invented(project):
    """PROVENANCE_MISSING should then fire for the real reason."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    assert one_unit(project).source_ids == ["RST-DSM", "RST-DEM"]


# --- identity and lineage, exactly as ingest does them -------------------------------

def test_the_building_is_attached_to_its_parcel_in_both_directions(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    uid = one_unit(project).unit_id
    edges = {(r["rel_type"], r["from_unit_id"], r["to_unit_id"]) for r in project.execute(
        "SELECT rel_type, from_unit_id, to_unit_id FROM unit_relationship")}
    assert edges == {("contains", "PCL-1", uid), ("inside", uid, "PCL-1")}


def test_an_accepted_building_gets_a_provisional_ulpin_under_its_parcel(project):
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    assert suggestions.apply(project, SETTINGS).minted == 1
    assert one_unit(project).ulpin_provisional.startswith(PARENT)


def test_a_building_over_no_parcel_gets_no_identifier(project):
    """The same refusal ingest makes: no parent, no identifier, never a placeholder."""
    raw = suggestion(ELSEWHERE)
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    report = suggestions.apply(project, SETTINGS)

    assert report.unresolved == [raw["suggestion_id"]]
    assert report.minted == 0
    assert one_unit(project).ulpin_provisional is None


def test_applying_twice_does_not_mint_a_second_building(project):
    """`unit_id` is allocated once. Re-applying after a further review is routine."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    first = suggestions.apply(project, SETTINGS)
    second = suggestions.apply(project, SETTINGS)

    assert (first.created, second.created, second.reused) == (1, 0, 1)
    assert project.execute("SELECT count(*) FROM unit WHERE unit_type='building'"
                           ).fetchone()[0] == 1


# --- a decision is not undone by re-running the model --------------------------------

def test_re_receiving_a_suggestion_does_not_erase_the_decision_on_it(project):
    """The detector re-runs constantly during a demo. Overwriting the row would silently
    return an accepted outline to the queue, or worse, resurrect a rejected one."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "rejected", "bibisha")

    report = suggestions.receive(project, [raw], SETTINGS)
    assert report.already_reviewed == [raw["suggestion_id"]]
    assert report.stored == 0
    row = project.execute("SELECT review_state, reviewed_by FROM ai_suggestion").fetchone()
    assert (row[0], row[1]) == ("rejected", "bibisha")


def test_a_pending_suggestion_is_refreshed_by_a_re_run(project):
    """The silence on the other side: nothing has been decided, so nothing is protected
    and a re-run may correct itself."""
    raw = suggestion(confidence=0.5)
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.receive(project, [raw | {"confidence": 0.9}], SETTINGS)
    assert project.execute("SELECT confidence FROM ai_suggestion").fetchone()[0] == 0.9


def test_a_suggestion_that_became_a_unit_cannot_be_re_decided(project):
    """Rewinding it would mean orphaning a unit or withdrawing an allocated identity."""
    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    suggestions.review(project, raw["suggestion_id"], "accepted", "bibisha")
    suggestions.apply(project, SETTINGS)

    with pytest.raises(suggestions.AlreadyApplied, match="already become unit"):
        suggestions.review(project, raw["suggestion_id"], "rejected", "bibisha")


# --- the review queue ----------------------------------------------------------------

def test_the_queue_reports_what_a_reviewer_needs_to_decide(project):
    a, b = suggestion(confidence=0.9), suggestion(ELSEWHERE, confidence=0.4)
    suggestions.receive(project, [a, b], SETTINGS)
    suggestions.review(project, a["suggestion_id"], "accepted", "bibisha")

    pending = suggestions.listing(project, "pending")
    assert [s["suggestion_id"] for s in pending] == [b["suggestion_id"]]
    assert pending[0]["confidence"] == 0.4
    assert pending[0]["attributes"]["floor_count"] == 5
    assert pending[0]["review"]["reviewed_by"] is None

    accepted = suggestions.listing(project, "accepted")
    assert accepted[0]["review"]["reviewed_by"] == "bibisha"


def _validate(conn):
    units = [store.get_unit(conn, r["unit_id"])
             for r in conn.execute("SELECT unit_id FROM unit")]
    rels = [Relationship(r["from_unit_id"], r["to_unit_id"], RelType(r["rel_type"]),
                         datetime.now(UTC))
            for r in conn.execute("SELECT * FROM unit_relationship")]
    sources = {"RST-DSM": Accuracy(0.20, 0.10), "RST-DEM": Accuracy(0.20, 0.10),
               "src-parcels": Accuracy(0.20, 0.25)}
    return validate.run(units, rels, sources, SETTINGS)


def test_the_stored_suggestion_still_satisfies_the_inbound_contract(project):
    """What comes back out of the queue is what P3 handed in - the round trip through
    SQLite must not quietly reshape a payload another block generates types from."""
    import pathlib

    from jsonschema import Draft202012Validator
    schema = Draft202012Validator(json.loads(
        (suggestions.SCHEMA_PATH).read_text()))
    assert pathlib.Path(suggestions.SCHEMA_PATH).exists()

    raw = suggestion()
    suggestions.receive(project, [raw], SETTINGS)
    out = suggestions.listing(project)[0]
    del out["unit_id"]                      # our bookkeeping, not part of the contract
    assert not [e.message for e in schema.iter_errors(out)]
