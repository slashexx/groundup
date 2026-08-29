"""Property-based tests for the geometric core.

The prism decomposition is the single load-bearing simplification in the whole block:

    two units intersect  iff  footprints intersect  AND  z-intervals overlap

If that is wrong, every overlap, gap and crossing result is wrong with it.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from cadastre.models import Accuracy, CreatedBy, Representation, Status, Unit, UnitType
from cadastre.validate import tolerance
from cadastre.validate.rules._util import z_overlap

coords = st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False)
tols = st.floats(min_value=0, max_value=5, allow_nan=False, allow_infinity=False)
accs = st.builds(Accuracy,
                 st.floats(min_value=0, max_value=10, allow_nan=False),
                 st.floats(min_value=0, max_value=10, allow_nan=False))


def _prism(lo, hi):
    return Unit(unit_id="u", unit_type=UnitType.FLOOR, status=Status.DRAFT,
                crs="EPSG:32643", vertical_datum="EGM2008",
                footprint_2d={"type": "Polygon", "coordinates": []},
                source_ids=["s"], created_by=CreatedBy.HUMAN,
                representation=Representation.PRISM,
                lower_limit=min(lo, hi), upper_limit=max(lo, hi))


@given(coords, coords, coords, coords, tols)
def test_z_overlap_is_symmetric(a1, a2, b1, b2, tol):
    a, b = _prism(a1, a2), _prism(b1, b2)
    assert z_overlap(a, b, tol) == z_overlap(b, a, tol)


@given(coords, coords, coords, tols)
def test_touching_intervals_never_overlap(a1, a2, span, tol):
    """One floor's ceiling is the next one's slab. That is contact, not intersection -
    if this were an overlap, every correctly modelled building would fail validation.
    """
    lo, hi = min(a1, a2), max(a1, a2)
    below, above = _prism(lo, hi), _prism(hi, hi + abs(span))
    assert not z_overlap(below, above, tol)


@given(coords, coords, coords, coords)
def test_separated_intervals_never_overlap_at_zero_tolerance(a1, a2, gap, span):
    lo, hi = min(a1, a2), max(a1, a2)
    start = hi + abs(gap) + 1e-6
    assert not z_overlap(_prism(lo, hi), _prism(start, start + abs(span)), 0.0)


@given(accs, accs, st.floats(min_value=0.1, max_value=3, allow_nan=False))
def test_tolerance_is_symmetric_and_never_negative(a, b, k):
    h1, v1 = tolerance.combined(a, b, k)
    h2, v2 = tolerance.combined(b, a, k)
    assert (h1, v1) == (h2, v2)
    assert h1 >= 0 and v1 >= 0


@given(accs, accs, st.floats(min_value=0.1, max_value=3, allow_nan=False))
def test_tolerance_is_at_least_the_worse_input(a, b, k):
    """Combining two measurements can never produce more confidence than either alone."""
    h, v = tolerance.combined(a, b, k)
    assert h >= max(a.horizontal_m, b.horizontal_m) * k - 1e-9
    assert v >= max(a.vertical_m, b.vertical_m) * k - 1e-9
