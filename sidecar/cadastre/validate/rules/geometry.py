"""Per-unit geometric sanity. Cheap - safe to run on every save."""

from __future__ import annotations

import hashlib

from shapely import to_wkb

from ...models import Finding, RuleId, Severity
from ._util import finding


def invalid(ctx, run_id: str) -> list[Finding]:
    out = []
    for uid, g in ctx.geoms.items():
        if not g.is_valid:
            out.append(finding(
                run_id, RuleId.GEOM_INVALID, Severity.ERROR, uid,
                "Footprint is not a valid polygon (self-intersection, repeated vertices "
                "or an unclosed ring).",
                geometry=ctx.units[uid].footprint_2d,
                action="Repair the footprint before the unit can be approved."))
    return out


def impossible_z(ctx, run_id: str) -> list[Finding]:
    out = []
    for uid, u in ctx.units.items():
        if u.lower_limit is None or u.upper_limit is None:
            continue
        if u.lower_limit >= u.upper_limit:
            out.append(finding(
                run_id, RuleId.Z_IMPOSSIBLE, Severity.ERROR, uid,
                f"Lower limit {u.lower_limit} is not below upper limit {u.upper_limit}.",
                measured=u.upper_limit - u.lower_limit,
                action="Correct the height range; a unit must enclose a positive volume."))
    return out


def duplicate(ctx, run_id: str) -> list[Finding]:
    """Same normalised footprint AND the same z-range. Either alone is legitimate:
    every floor of a building shares one footprint.
    """
    seen: dict[tuple, str] = {}
    out = []
    for uid, u in ctx.units.items():
        key = (hashlib.sha256(to_wkb(ctx.geoms[uid].normalize())).hexdigest(),
               u.lower_limit, u.upper_limit)
        if key in seen:
            out.append(finding(
                run_id, RuleId.GEOM_DUPLICATE, Severity.ERROR, uid,
                f"Identical footprint and height range to {seen[key]}.",
                related=[seen[key]], geometry=u.footprint_2d,
                action="Merge the duplicates or correct one of the height ranges."))
        else:
            seen[key] = uid
    return out
