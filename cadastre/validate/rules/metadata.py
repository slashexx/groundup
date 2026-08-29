"""Non-spatial checks: provenance completeness and reference-system agreement.

A uniform vertical offset applied to everything is invisible here - every relative
relationship stays consistent. This module can only catch sources that DISAGREE with
each other, which is why the ingest block must record vertical_datum per source.
"""

from __future__ import annotations

from ...models import Finding, Unit


def crs_mismatch(units: list[Unit], ctx) -> list[Finding]:
    raise NotImplementedError


def datum_mismatch(units: list[Unit], ctx) -> list[Finding]:
    raise NotImplementedError


def provenance_missing(units: list[Unit], ctx) -> list[Finding]:
    """Null source_ids, accuracy or confidence -> Info."""
    raise NotImplementedError


def confidence_low(units: list[Unit], ctx) -> list[Finding]:
    raise NotImplementedError
