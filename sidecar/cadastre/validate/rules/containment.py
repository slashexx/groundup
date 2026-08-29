"""Parent containment and utility conflicts - both type-conditional.

Underground and elevated units are easements, not ownership volumes. Crossing a parcel
boundary is their normal condition; a tunnel confined to a single parcel would be the
anomaly. Crossing an *ownership volume* is still an error - a water main through
someone's flat.

    ownership volumes must not overlap. easement corridors are supposed to.
"""

from __future__ import annotations

from ...models import Finding, RuleId, Severity, UnitType
from .. import tolerance
from ._util import finding, shrink, z_overlap

#: Volumes a utility must not pass through. Buildings are deliberately absent: a building
#: is an aggregate of its floors, so reporting both it and the penetrated floor is
#: duplicate noise. Buildings with no modelled floors are added back at runtime.
PENETRABLE = (UnitType.FLOOR, UnitType.APARTMENT)


def escapes_parent(ctx, run_id: str) -> list[Finding]:
    out = []
    for uid, u in ctx.units.items():
        if u.unit_type.is_easement:
            continue                        # an easement leaving its parcel is expected
        pid = ctx.parent.get(uid)
        if pid is None:
            continue
        tol_h, tol_v = tolerance.pair(ctx, uid, pid)
        outside = shrink(ctx.geoms[uid], tol_h).difference(ctx.geoms[pid])
        parent = ctx.units[pid]

        if outside.area > tolerance.negligible_area(tol_h):
            out.append(finding(
                run_id, RuleId.ESCAPES_PARENT, Severity.ERROR, uid,
                f"{outside.area:.2f} m2 of {uid} lies outside its parent {pid}.",
                related=[pid], geometry=outside.__geo_interface__,
                measured=round(outside.area, 2),
                action="Correct the boundary, or reassign the unit to the right parent."))
            continue

        if None in (u.lower_limit, u.upper_limit, parent.lower_limit, parent.upper_limit):
            continue
        if u.lower_limit < parent.lower_limit - tol_v or u.upper_limit > parent.upper_limit + tol_v:
            out.append(finding(
                run_id, RuleId.ESCAPES_PARENT, Severity.ERROR, uid,
                f"Height range {u.lower_limit}-{u.upper_limit} extends beyond parent "
                f"{pid} ({parent.lower_limit}-{parent.upper_limit}).",
                related=[pid], tolerance=round(tol_v, 3),
                action="Correct the height range, or extend the parent."))
    return out


def utility_crosses_building(ctx, run_id: str) -> list[Finding]:
    targets = {uid for uid, u in ctx.units.items() if u.unit_type in PENETRABLE}
    # A building whose floors were never modelled is itself the finest volume available.
    for uid, u in ctx.units.items():
        if u.unit_type is UnitType.BUILDING and not any(
            ctx.units[c].unit_type is UnitType.FLOOR for c in ctx.children.get(uid, [])
        ):
            targets.add(uid)

    out = []
    for uid, u in ctx.units.items():
        if not u.unit_type.is_easement:
            continue
        for oid in ctx.candidates(uid):
            if oid not in targets:
                continue
            other = ctx.units[oid]
            tol_h, tol_v = tolerance.pair(ctx, uid, oid)
            if not z_overlap(u, other, tol_v):
                continue
            if not shrink(ctx.geoms[uid], tol_h).intersects(shrink(ctx.geoms[oid], tol_h)):
                continue
            inter = ctx.geoms[uid].intersection(ctx.geoms[oid])
            kind = u.attributes.get("utility_kind", u.unit_type.value)
            out.append(finding(
                run_id, RuleId.UTILITY_CROSSES_BUILDING, Severity.ERROR, uid,
                f"{kind} corridor {uid} passes through {oid} "
                f"({other.lower_limit}-{other.upper_limit} m) over {inter.area:.2f} m2.",
                related=[oid], geometry=inter.__geo_interface__,
                measured=round(inter.area, 2),
                action="Reroute the corridor, or record an easement over the affected "
                       "unit. Crossing a parcel is fine; crossing an ownership volume "
                       "is not."))
    return out
