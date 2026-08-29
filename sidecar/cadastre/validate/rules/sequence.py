"""Floor ordering, contiguity and plausibility."""

from __future__ import annotations

import itertools

from ...models import Finding, RuleId, Severity, UnitType
from .. import tolerance
from ._util import finding


def _floors_by_building(ctx) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pid, kids in ctx.children.items():
        fl = [k for k in kids if ctx.units[k].unit_type is UnitType.FLOOR
              and ctx.units[k].attributes.get("floor_index") is not None]
        if fl:
            out[pid] = sorted(fl, key=lambda k: ctx.units[k].attributes["floor_index"])
    return out


def floor_sequence(ctx, run_id: str) -> list[Finding]:
    """Consecutive floors must meet: one floor's ceiling is the next one's slab.

    A gap means unmodelled space; an inversion means the height model is wrong. Either
    way the stack no longer describes a real building.
    """
    out = []
    for floors in _floors_by_building(ctx).values():
        for below, above in itertools.pairwise(floors):
            b, a = ctx.units[below], ctx.units[above]
            if None in (b.upper_limit, a.lower_limit):
                continue
            _, tol_v = tolerance.pair(ctx, below, above)
            delta = a.lower_limit - b.upper_limit
            if abs(delta) <= tol_v:
                continue
            word = "gap" if delta > 0 else "overlap"
            out.append(finding(
                run_id, RuleId.FLOOR_SEQUENCE, Severity.ERROR, above,
                f"{abs(delta):.2f} m {word} between {below} (ends {b.upper_limit}) and "
                f"{above} (starts {a.lower_limit}). Floors must be contiguous.",
                related=[below], measured=round(abs(delta), 2), tolerance=round(tol_v, 3),
                action="Correct the slab heights so consecutive floors meet."))
    return out


def floor_height_plausible(ctx, run_id: str) -> list[Finding]:
    """Outside 2.4-5.0 m, either the floor count or the height model is wrong.

    A warning rather than an error: a 5.5 m ground floor is entirely plausible for
    retail, so a reviewer should decide rather than be blocked.
    """
    s = ctx.settings
    out = []
    for uid, u in ctx.units.items():
        if u.unit_type is not UnitType.FLOOR or u.height is None:
            continue
        if s.min_floor_height_m <= u.height <= s.max_floor_height_m:
            continue
        out.append(finding(
            run_id, RuleId.FLOOR_HEIGHT_IMPLAUSIBLE, Severity.WARNING, uid,
            f"Floor height {u.height:.2f} m is outside the plausible range "
            f"{s.min_floor_height_m}-{s.max_floor_height_m} m.",
            measured=round(u.height, 2),
            action="Check the floor count and the roof/ground estimates. Acknowledge if "
                   "the building genuinely has an unusual storey height."))
    return out
