"""The fixture is the specification.

`expected_findings` says what a correct validator must report. `must_not_fire` says what
it must stay silent about - and that half matters more. A validation engine that flags
everything is not cautious, it is useless: reviewers stop reading, and the human-in-the-
loop guarantee the whole system rests on quietly evaporates.
"""

from __future__ import annotations

from cadastre.models import Severity, ValidationState


def _key(f):
    return (f.rule_id.value, f.unit_id, tuple(sorted(f.related_unit_ids)))


def _expected_keys(raw):
    return {(e["rule_id"], e["unit_id"], tuple(sorted(e["related_unit_ids"])))
            for e in raw["expected_findings"]}


def test_every_expected_finding_is_reported(result, bundle):
    got, want = {_key(f) for f in result.findings}, _expected_keys(bundle["raw"])
    assert want - got == set(), f"expected findings not reported: {sorted(want - got)}"


def test_no_unexpected_findings(result, bundle):
    got, want = {_key(f) for f in result.findings}, _expected_keys(bundle["raw"])
    assert got - want == set(), f"spurious findings reported: {sorted(got - want)}"


def test_must_not_fire(result, bundle):
    """Negative tests. The important one: UGF-001 leaves both parcels and must NOT raise
    ESCAPES_PARENT, because an easement is not an ownership volume. A validator that
    flags it has implemented containment unconditionally and is wrong.
    """
    for case in bundle["raw"]["must_not_fire"]:
        offenders = [f for f in result.findings
                     if f.rule_id.value == case["rule_id"]
                     and (f.unit_id == case["unit_id"]
                          or case["unit_id"] in f.related_unit_ids)]
        assert not offenders, f"{case['rule_id']} fired on {case['unit_id']}: {case['note']}"


def test_severities_match(result, bundle):
    want = {(e["rule_id"], e["unit_id"]): e["severity"] for e in bundle["raw"]["expected_findings"]}
    for f in result.findings:
        k = (f.rule_id.value, f.unit_id)
        if k in want:
            assert f.severity.value == want[k], f"{k} severity {f.severity.value} != {want[k]}"


def test_measured_values_match(result, bundle):
    """Geometry is axis-aligned precisely so these are exact, not approximate."""
    want = {(e["rule_id"], e["unit_id"]): e["measured_value"]
            for e in bundle["raw"]["expected_findings"] if e["measured_value"] is not None}
    for f in result.findings:
        k = (f.rule_id.value, f.unit_id)
        if k in want:
            assert f.measured_value == want[k], f"{k}: {f.measured_value} != {want[k]}"


def test_errors_block_approval_warnings_do_not_on_their_own(result):
    assert not result.approvable("APT-102")          # OVERLAP_SIBLING
    assert not result.approvable("FLR-005")          # FLOOR_SEQUENCE
    assert not result.approvable("FLR-000")          # unacknowledged warning
    assert result.approvable("FLR-002")              # clean

    for f in result.findings:
        if f.unit_id == "FLR-000" and f.severity is Severity.WARNING:
            f.acknowledged_by = "reviewer"
    assert result.approvable("FLR-000"), "an acknowledged warning must not block approval"


def test_validation_state_reflects_worst_finding(result):
    assert result.state_of("APT-102") is ValidationState.FAILED
    assert result.state_of("FLR-002") is ValidationState.PASSED


def test_tolerance_is_recorded_so_a_reviewer_can_see_why(result):
    """A finding without the threshold it was compared against is unarguable."""
    needs_threshold = {"OVERLAP_SIBLING", "FLOOR_SEQUENCE"}
    for f in result.findings:
        if f.rule_id.value in needs_threshold:
            assert f.tolerance is not None, f"{f.rule_id.value} on {f.unit_id}"
