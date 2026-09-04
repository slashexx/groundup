"""The missing link: registered rasters -> heights -> floors.

`ingest_gpkg` deliberately imports footprints with no heights, because P2 registers
rasters but does not deliver elevation through the GeoPackage. `extrude` can derive
heights but does not know where the project's rasters live. This joins the two.

Nothing here invents a height. A building whose footprint no registered raster covers is
left exactly as ingest produced it, with `heights_unavailable` recorded and
HEIGHTS_UNAVAILABLE raised at validation - visible in the review queue rather than
silently absent.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

import shapely.geometry
import shapely.wkb

from .extrude import floors as flr
from .extrude import raster
from .models import (
    CreatedBy,
    ProjectSettings,
    Relationship,
    RelType,
    Representation,
    Status,
    Unit,
    UnitType,
)
from .store import get_unit, load_project, save_relationship, save_unit
from .ulpin import ledger
from .ulpin.encode import Stratum, format_ulpin, parse_ulpin


@dataclass
class DeriveReport:
    parcels_grounded: int = 0
    buildings_seen: int = 0
    heights_derived: int = 0
    floors_created: int = 0
    floors_identified: int = 0          # derived floors that got a provisional ULPIN
    skipped_no_raster: list[str] = field(default_factory=list)
    skipped_thin_coverage: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "parcels_grounded": self.parcels_grounded,
            "buildings_seen": self.buildings_seen,
            "heights_derived": self.heights_derived,
            "floors_created": self.floors_created,
            "floors_identified": self.floors_identified,
            "skipped_no_raster": self.skipped_no_raster,
            "skipped_thin_coverage": self.skipped_thin_coverage,
        }


def _rasters(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Registered rasters by kind. Paths are relative to the project folder."""
    try:
        rows = conn.execute("SELECT raster_id, kind, path, source_id FROM raster").fetchall()
    except sqlite3.OperationalError:
        return {}
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["kind"].upper(), []).append(dict(r))
    return out


def derive_heights(conn: sqlite3.Connection, *, default_floor_count: int = 1) -> DeriveReport:
    """Give every un-extruded building a height range and a floor stack.

    `default_floor_count` is used only when the footprint carried no storey count from
    the source. It is not a guess about the building - one floor spanning the whole
    derived height is the honest representation of "we measured the envelope but were
    not told how it is divided", and validation flags an implausible storey height if
    that envelope is too tall to be a single floor.
    """
    report = DeriveReport()
    by_kind = _rasters(conn)
    dem = by_kind.get("DEM", [{}])[0].get("path")
    dsm = by_kind.get("DSM", [{}])[0].get("path")

    _, _, _, settings = load_project(conn)

    if dem:
        report.parcels_grounded = _ground_parcels(conn, dem, settings)

    rows = conn.execute(
        "SELECT unit_id FROM unit WHERE unit_type = ? AND lower_limit IS NULL",
        (UnitType.BUILDING.value,),
    ).fetchall()

    for row in rows:
        report.buildings_seen += 1
        building = get_unit(conn, row["unit_id"])
        if building is None:
            continue
        if not dem or not dsm:
            report.skipped_no_raster.append(building.unit_id)
            continue

        footprint = shapely.geometry.shape(building.footprint_2d)
        try:
            rebuilt = _rebuild(building, footprint, dem, dsm, settings)
        except raster.NoCoverage:
            report.skipped_no_raster.append(building.unit_id)
            continue
        if rebuilt.lower_limit is None:
            report.skipped_thin_coverage.append(building.unit_id)
            save_unit(conn, rebuilt)
            continue

        _ensure_parcel_reference(rebuilt)
        save_unit(conn, rebuilt)
        report.heights_derived += 1

        count = int(rebuilt.attributes.get("floor_count") or default_floor_count)
        for floor in flr.split(rebuilt, count, settings):
            if _identify(conn, floor, settings):
                report.floors_identified += 1
            save_unit(conn, floor)
            save_relationship(conn, Relationship(
                rebuilt.unit_id, floor.unit_id, RelType.CONTAINS, datetime.now(UTC)))
            save_relationship(conn, Relationship(
                floor.unit_id, rebuilt.unit_id, RelType.INSIDE, datetime.now(UTC)))
            report.floors_created += 1

    conn.commit()
    return report


def _identify(conn: sqlite3.Connection, floor: Unit, settings: ProjectSettings) -> bool:
    """Give a derived floor its provisional ULPIN. Returns whether one was minted.

    `04-ulpin.md` says a unit in `needs_review` carries a provisional identifier that may
    be recomputed freely; only `approved` freezes one. Derived floors were the single kind
    that carried none, so the published record showed a raw uuid4 where the identifier
    belongs - on the very units that *are* the vertical subdivision this project exists to
    identify. The fixture has always given its floors `A00-000`, `A01-000`, `B01-000`;
    live data did not, and the divergence only became visible once P6 published it.

    The stratum comes from the sign of `floor_index`, which is how `extrude.floors`
    already encodes basements, and the level is its magnitude. The sequence is allocated
    through the ledger, never derived from geometry - see the determinism trap in
    `04-ulpin.md`. Allocation is keyed by `unit_id`, so re-running derive over a floor
    that already holds a number returns the same one.

    No parent, no identifier: a floor whose building never carried `parent_ulpin_14` is
    left with none rather than minted under a placeholder parent, the same refusal ingest
    makes for a parcel with no parent ULPIN.
    """
    parent = floor.attributes.get("parent_ulpin_14")
    if not parent:
        return False
    index = int(floor.attributes.get("floor_index", 0))
    stratum = Stratum.ABOVE if index >= 0 else Stratum.BELOW
    level = abs(index)
    if level > 99:                    # the format holds two digits; refuse rather than wrap
        return False
    seq = ledger.allocate_sequence(conn, str(parent), stratum.value, level, floor.unit_id)
    version = int(str(settings.ulpin_version).lstrip("vV") or 1)
    floor.ulpin_provisional = format_ulpin(str(parent), version, stratum, level, seq)
    floor.ulpin_version = settings.ulpin_version
    return True


def _rebuild(building: Unit, footprint, dem: str, dsm: str,
             settings: ProjectSettings) -> Unit:
    """Derive heights onto an existing building, keeping its identity and lineage."""
    from .extrude import building as bld

    fresh = bld.build(footprint, dem, dsm, settings, building.source_ids,
                      unit_id=building.unit_id)
    building.lower_limit = fresh.lower_limit
    building.upper_limit = fresh.upper_limit
    building.representation = Representation.PRISM
    building.created_by = CreatedBy.DERIVED
    building.status = Status.NEEDS_REVIEW
    keep = {k: v for k, v in building.attributes.items() if k != "heights_unavailable"}
    building.attributes = keep | fresh.attributes
    return building


def _ground_parcels(conn: sqlite3.Connection, dem: str,
                    settings: ProjectSettings) -> int:
    """Anchor each parcel's legal column to the ground beneath it.

    `stratum_below_limit_m` and `stratum_above_limit_m` are **relative to ground level at
    the parcel**, not absolute heights in the vertical datum. A parcel's rights run some
    depth below and some height above its own surface; they do not run from the geoid.

    Read absolutely, a -30/+150 stratum over ground at 912 m puts the entire parcel
    column below its own buildings, and every structure on it raises ESCAPES_PARENT. That
    is exactly what the first end-to-end run produced.

    Ingest cannot do this - it has no elevation data and must not assert a ground level it
    has not measured. Here the DEM is available, so the column can be anchored honestly.
    """
    grounded = 0
    rows = conn.execute(
        "SELECT unit_id FROM unit WHERE unit_type = ?", (UnitType.LAND_PARCEL.value,)
    ).fetchall()
    for row in rows:
        parcel = get_unit(conn, row["unit_id"])
        if parcel is None:
            continue
        footprint = shapely.geometry.shape(parcel.footprint_2d)
        try:
            ground = raster.ground_level(dem, footprint)
        except raster.NoCoverage:
            continue
        parcel.lower_limit = ground + settings.stratum_below_limit_m
        parcel.upper_limit = ground + settings.stratum_above_limit_m
        parcel.attributes = parcel.attributes | {
            "ground_level_m": round(ground, 3),
            "stratum_is_relative_to_ground": True,
        }
        save_unit(conn, parcel)
        grounded += 1
    return grounded


def _ensure_parcel_reference(building: Unit) -> None:
    """Make the building's parcel explicit before its floors inherit from it.

    Ingest records `parent_ulpin_14` on parcels but not on the buildings inside them - a
    building instead carries a provisional ULPIN whose prefix *is* that parcel. That is
    enough to approve the building itself, because `freeze` uses the provisional string
    directly, but floors are minted fresh and have nothing to inherit, so every one of
    them failed at approval with UnknownParcel.

    The prefix is recovered from the building's own identifier rather than by walking the
    containment graph: it is the same fact, already present, and it cannot disagree with
    the identifier the building was issued.
    """
    if building.attributes.get("parent_ulpin_14"):
        return
    identifier = building.ulpin or building.ulpin_provisional
    if not identifier:
        return
    try:
        building.attributes = building.attributes | {
            "parent_ulpin_14": parse_ulpin(identifier)["parent_ulpin_14"]
        }
    except ValueError:
        pass          # malformed identifier is the ledger's business, not ours
