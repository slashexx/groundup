"""Property-based tests for ULPIN encoding.

Example-based tests confirm the cases we thought of. These confirm the cases we did not.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from cadastre.ulpin.encode import (
    ALPHABET, Stratum, check_char, format_ulpin, parse_ulpin, to_urn, verify,
)

parents = st.text(alphabet=ALPHABET, min_size=14, max_size=14)
versions = st.integers(min_value=1, max_value=99)
strata = st.sampled_from(list(Stratum))
levels = st.integers(min_value=0, max_value=99)
sequences = st.integers(min_value=0, max_value=999)


@given(parents, versions, strata, levels, sequences)
def test_roundtrip(parent, version, stratum, level, seq):
    u = format_ulpin(parent, version, stratum, level, seq)
    p = parse_ulpin(u)
    assert p == {"parent_ulpin_14": parent, "version": version,
                 "stratum": stratum, "level": level, "sequence": seq}


@given(parents, versions, strata, levels, sequences)
def test_minting_is_deterministic(parent, version, stratum, level, seq):
    """Same inputs, same output - always. FR-06's determinism requirement applies to the
    minting function; the lifetime binding is frozen separately at approval.
    """
    a = format_ulpin(parent, version, stratum, level, seq)
    b = format_ulpin(parent, version, stratum, level, seq)
    assert a == b and verify(a)


@given(parents, versions, strata, levels, sequences,
       st.integers(min_value=0, max_value=26), st.sampled_from(ALPHABET))
@settings(max_examples=400)
def test_any_single_substitution_is_caught(parent, version, stratum, level, seq, pos, ch):
    """The check character must reject every single-character corruption."""
    u = format_ulpin(parent, version, stratum, level, seq)
    if pos >= len(u) or u[pos] == ch or u[pos] == "-":
        return
    assert not verify(u[:pos] + ch + u[pos + 1:])


@given(parents, versions, strata, levels, sequences)
def test_parent_prefix_is_preserved_verbatim(parent, version, stratum, level, seq):
    """Every existing 2D Bhu-Aadhaar record must still resolve, and a lexical sort must
    group units by parcel. Both depend on the prefix being untouched.
    """
    assert format_ulpin(parent, version, stratum, level, seq).startswith(parent + "-")


@given(parents, versions, strata, levels, sequences)
def test_urn_carries_the_same_information(parent, version, stratum, level, seq):
    u = format_ulpin(parent, version, stratum, level, seq)
    assert to_urn(u).split(":") [4] == parent


@given(st.text(alphabet=ALPHABET, min_size=1, max_size=40))
def test_check_char_is_always_in_the_alphabet(body):
    assert check_char(body) in ALPHABET


@given(st.text(min_size=0, max_size=30))
def test_garbage_never_verifies(s):
    assert not verify(s)
