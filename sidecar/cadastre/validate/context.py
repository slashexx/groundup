"""Everything a rule needs, computed once per run.

Built here rather than inside each rule so the STRtree and the containment graph are
constructed a single time. Rules are pure functions of this context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely import STRtree
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from ..models import Accuracy, ProjectSettings, RelType, Relationship, Unit

#: Used when a unit's sources declare no accuracy. Deliberately large: with provenance
#: unknown we must not manufacture a confident tolerance. PROVENANCE_MISSING is raised
#: separately so the gap is visible rather than silently absorbed.
UNKNOWN_ACCURACY = Accuracy(horizontal_m=1.0, vertical_m=1.0)


@dataclass
class Context:
    units: dict[str, Unit]
    geoms: dict[str, BaseGeometry]
    settings: ProjectSettings
    accuracy: dict[str, Accuracy]
    accuracy_known: dict[str, bool]
    parent: dict[str, str] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)
    _tree: STRtree | None = None
    _order: list[str] = field(default_factory=list)

    def candidates(self, unit_id: str) -> list[str]:
        """Spatially plausible neighbours. Never O(n^2)."""
        if self._tree is None:
            return [u for u in self.units if u != unit_id]
        hits = self._tree.query(self.geoms[unit_id])
        return [self._order[i] for i in hits if self._order[i] != unit_id]

    def siblings(self, unit_id: str) -> list[str]:
        p = self.parent.get(unit_id)
        if p is None:
            return []
        return [c for c in self.children.get(p, []) if c != unit_id]


def build(units: list[Unit], relationships: list[Relationship],
          sources: dict[str, Accuracy | None], settings: ProjectSettings) -> Context:
    by_id = {u.unit_id: u for u in units}
    geoms = {u.unit_id: shape(u.footprint_2d) for u in units}

    acc: dict[str, Accuracy] = {}
    known: dict[str, bool] = {}
    for u in units:
        declared = [sources.get(s) for s in u.source_ids]
        present = [a for a in declared if a is not None]
        known[u.unit_id] = bool(present) and len(present) == len(declared)
        # Worst case across contributing sources - a unit is only as good as its
        # weakest input.
        acc[u.unit_id] = (
            Accuracy(max(a.horizontal_m for a in present), max(a.vertical_m for a in present))
            if present else UNKNOWN_ACCURACY
        )

    parent: dict[str, str] = {}
    children: dict[str, list[str]] = {}
    for r in relationships:
        if r.rel_type is RelType.CONTAINS:
            children.setdefault(r.from_unit_id, []).append(r.to_unit_id)
            parent[r.to_unit_id] = r.from_unit_id

    ctx = Context(units=by_id, geoms=geoms, settings=settings,
                  accuracy=acc, accuracy_known=known, parent=parent, children=children)
    ctx._order = list(by_id)
    ctx._tree = STRtree([geoms[u] for u in ctx._order])
    return ctx
