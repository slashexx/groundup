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


def heights_unavailable(ctx, run_id: str) -> list[Finding]:
    """A unit with no vertical extent is not a volume, and must not receive an identifier.

    Storing an unknown height as None is correct (FR-03 forbids guessing it). But storing
    it is not the same as reporting it: every other rule *skips* a unit whose limits are
    None - overlap cannot overlap, containment cannot escape, ordering cannot invert - so
    such a unit sails through validation with zero findings and reads as clean in the
    review queue.

    Found end to end: a building ingested without any elevation raster had
    z=[None, None], produced no findings at all, and was approved through the API,
    receiving a permanent 3D ULPIN for something with no third dimension.

    An error rather than a warning: a provisional record may certainly lack heights while
    the rasters are still being fitted, but the identifier minted at approval is
    permanent, and issuing one over an unmeasured volume is exactly what this system
    exists to prevent.
    """
    out = []
    for uid, u in ctx.units.items():
        missing = [n for n, v in (("lower_limit", u.lower_limit),
                                  ("upper_limit", u.upper_limit)) if v is None]
        if not missing:
            continue
        why = u.attributes.get("heights_unavailable")
        out.append(finding(
            run_id, RuleId.HEIGHTS_UNAVAILABLE, Severity.ERROR, uid,
            f"{uid} has no vertical extent ({', '.join(missing)} unknown)"
            + (f": {why}." if why else ".")
            + " A unit without heights is not a volume and cannot carry a 3D identifier.",
            geometry=u.footprint_2d,
            action="Supply elevation data covering this footprint and re-derive the "
                   "heights, or enter them manually. Do not approve until then."))
    return out


def duplicate(ctx, run_id: str) -> list[Finding]:
    """Same normalised footprint AND the same z-range. Either alone is legitimate:
    every floor of a building shares one footprint.

    A unit and its own parent are exempt. A single-storey building has exactly one floor,
    and that floor necessarily has the building's footprint and the building's height
    range - the two coincide because the building *is* one storey, not because a record
    was entered twice. Flagging it made every single-storey building in a project
    unapprovable, which over rural India is most of them.

    The exemption is deliberately narrow: only the pair actually related by containment.
    Two sibling floors at the same level, or two buildings entered twice, still collide.
    """
    seen: dict[tuple, str] = {}
    out = []
    for uid, u in ctx.units.items():
        key = (hashlib.sha256(to_wkb(ctx.geoms[uid].normalize())).hexdigest(),
               u.lower_limit, u.upper_limit)
        first = seen.get(key)
        if first is None:
            seen[key] = uid
            continue
        if ctx.parent.get(uid) == first or ctx.parent.get(first) == uid:
            continue                    # a unit and the thing containing it
        out.append(finding(
            run_id, RuleId.GEOM_DUPLICATE, Severity.ERROR, uid,
            f"Identical footprint and height range to {first}.",
            related=[first], geometry=u.footprint_2d,
            action="Merge the duplicates or correct one of the height ranges."))
    return out
