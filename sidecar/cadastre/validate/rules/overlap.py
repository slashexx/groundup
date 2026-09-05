"""Sibling overlap and gap detection.

No 3D boolean engine is needed, because every unit is a prism:

    two units intersect  iff  footprints intersect  AND  z-intervals overlap

The inward buffer by the horizontal tolerance is what separates a shared wall (adjacent
flats touch by definition - normal) from real penetration (a finding).
"""

from __future__ import annotations

from shapely.ops import unary_union

from ...models import Finding, RuleId, Severity
from .. import tolerance
from ._util import finding, shrink, z_overlap


def siblings_overlap(ctx, run_id: str) -> list[Finding]:
    """Ownership volumes must not overlap.

    Easements are exempt on both sides: a utility corridor is *supposed* to pass through
    the parcels above it. Utility-versus-ownership conflicts are the job of
    containment.utility_crosses_building, which reports against the specific volume
    penetrated instead of every container of it.
    """
    out, done = [], set()
    for uid, u in ctx.units.items():
        if u.unit_type.is_easement:
            continue
        for oid in ctx.candidates(uid):
            other = ctx.units[oid]
            if ctx.parent.get(uid) != ctx.parent.get(oid):
                continue
            # Peers only. Overlap between *different* types is containment - a parcel's
            # footprint covers its buildings, a floor's covers its apartments - and that
            # is what escapes_parent and the relationship graph are for. Comparing across
            # types reports a parcel as overlapping the building standing on it, which is
            # both wrong and the loudest possible finding on a perfectly ordinary site.
            if other.unit_type is not u.unit_type:
                continue
            key = tuple(sorted((uid, oid)))
            if key in done:
                continue
            done.add(key)

            tol_h, tol_v = tolerance.pair(ctx, uid, oid)
            if not z_overlap(u, other, tol_v):
                continue
            ga, gb = ctx.geoms[uid], ctx.geoms[oid]
            if not shrink(ga, tol_h).intersects(shrink(gb, tol_h)):
                continue

            inter = ga.intersection(gb)
            # `shrink` returns the original geometry when erosion would annihilate it,
            # so a unit narrower than its own tolerance is compared unbuffered - and two
            # that merely share a wall then register as intersecting with zero area.
            # Dense real footprints are full of these; a 0.00 m2 "overlap" is exactly the
            # noise that teaches reviewers to stop reading findings.
            if inter.area <= tolerance.negligible_area(tol_h):
                continue

            out.append(finding(
                run_id, RuleId.OVERLAP_SIBLING, Severity.ERROR, key[0],
                f"Ownership volumes {key[0]} and {key[1]} overlap by "
                f"{inter.area:.2f} m2 over a shared height range.",
                related=[key[1]], geometry=inter.__geo_interface__,
                measured=round(inter.area, 2), tolerance=round(tol_h, 3),
                action="Adjust one boundary; two ownership volumes cannot occupy the "
                       "same space."))
    return out


def gap_against_parent(ctx, run_id: str) -> list[Finding]:
    """Children that claim to tile their parent but leave uncovered area.

    Only checked where the parent declares `subdivided: true`. A floor with no interior
    data is not making a tiling claim, and checking it would flag every real building.

    This is a WARNING, not an error: corridors, lift shafts and stairwells legitimately
    leave gaps when only the apartments are modelled.
    """
    out = []
    for pid, kids in ctx.children.items():
        parent = ctx.units[pid]
        if not parent.attributes.get("subdivided"):
            continue
        tol_h, _ = tolerance.self_(ctx, pid)
        # Dilate the children by the tolerance so a seam narrower than measurement error
        # is not reported as uncovered space.
        covered = unary_union([ctx.geoms[k] for k in kids]).buffer(tol_h)
        missing = ctx.geoms[pid].difference(covered)
        limit = tolerance.negligible_area(tol_h)
        if missing.area > limit:
            out.append(finding(
                run_id, RuleId.GAP_SIBLING, Severity.WARNING, pid,
                f"{missing.area:.2f} m2 of {pid} is not covered by any child unit.",
                related=sorted(kids), geometry=missing.__geo_interface__,
                measured=round(missing.area, 2), tolerance=round(limit, 2),
                action="Expected where common areas are unmodelled. Acknowledge, or add "
                       "the missing units."))
    return out
