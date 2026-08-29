"""Non-spatial checks: reference-system agreement and provenance completeness.

A uniform vertical offset applied to everything is invisible here - every relative
relationship stays consistent. We can only catch sources that DISAGREE with each other,
which is why the ingest contract requires vertical_datum per source.
"""

from __future__ import annotations

from ...models import CreatedBy, Finding, RuleId, Severity
from ._util import finding


def crs_mismatch(ctx, run_id: str) -> list[Finding]:
    want = ctx.settings.project_crs
    return [
        finding(run_id, RuleId.CRS_MISMATCH, Severity.ERROR, uid,
                f"Unit CRS {u.crs} does not match the project CRS {want}.",
                action="Reproject during ingest. Mixed CRS makes every area and distance "
                       "comparison meaningless.")
        for uid, u in ctx.units.items() if u.crs != want
    ]


def datum_mismatch(ctx, run_id: str) -> list[Finding]:
    want = ctx.settings.vertical_datum
    return [
        finding(run_id, RuleId.DATUM_MISMATCH, Severity.ERROR, uid,
                f"Vertical datum {u.vertical_datum} does not match the project datum {want}.",
                action="Transform heights during ingest. Note that a uniform offset "
                       "applied to every source cannot be detected here at all.")
        for uid, u in ctx.units.items() if u.vertical_datum != want
    ]


def provenance_missing(ctx, run_id: str) -> list[Finding]:
    """No accuracy means no tolerance can be derived for this unit."""
    out = []
    for uid, u in ctx.units.items():
        if not u.source_ids:
            out.append(finding(
                run_id, RuleId.PROVENANCE_MISSING, Severity.INFO, uid,
                "Unit has no source references.",
                action="Link the unit to the data it was derived from."))
        elif not ctx.accuracy_known[uid]:
            out.append(finding(
                run_id, RuleId.PROVENANCE_MISSING, Severity.INFO, uid,
                f"No accuracy declared for one or more of {', '.join(u.source_ids)}, so "
                "no comparison tolerance can be derived for this unit.",
                action="Record horizontal and vertical accuracy on the source. If it is "
                       "genuinely unknown, enter a conservative estimate rather than "
                       "leaving it null."))
    return out


def confidence_low(ctx, run_id: str) -> list[Finding]:
    limit = ctx.settings.confidence_warn_below
    out = []
    for uid, u in ctx.units.items():
        if u.created_by is not CreatedBy.AI or u.confidence_score is None:
            continue
        if u.confidence_score < limit:
            out.append(finding(
                run_id, RuleId.CONFIDENCE_LOW, Severity.WARNING, uid,
                f"Model confidence {u.confidence_score:.2f} is below the review "
                f"threshold {limit}.",
                measured=u.confidence_score, tolerance=limit,
                action="Inspect the underlying evidence before approving."))
    return out
