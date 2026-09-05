"""P2's harmonized GeoPackage -> our units and relationships.

This is our side of `contracts/inbound/p2-geopackage.md`. P2 owns that schema; we are a
consumer, so everything here reads and nothing here writes to P2's tables.

Three things this module deliberately refuses to do:

* **Invent a parent ULPIN.** A parcel row with no `parent_ulpin_14` gets no provisional
  identifier at all. Minting one under a placeholder parent would produce a
  well-formed string naming land nobody chose - the same failure `ledger.UnknownParcel`
  exists to prevent, arriving one layer earlier.
* **Invent heights.** P2 registers rasters but does not deliver DEM/DSM through the
  GeoPackage, so every imported unit has `lower_limit`/`upper_limit` of None. That is
  FR-03: absent data is represented as absent, and `extrude` fills it in later when
  rasters exist.
* **Guess which parcel a building belongs to.** See `MAJORITY` below.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import shapely.geometry
import shapely.wkb
from shapely.geometry.base import BaseGeometry

from .models import (
    CreatedBy,
    ProjectSettings,
    Relationship,
    RelType,
    Status,
    Unit,
    UnitType,
)
from .store import save_relationship, save_unit
from .ulpin import ledger
from .ulpin.encode import Stratum, format_ulpin

#: A footprint is assigned to a parcel only when that parcel holds MORE than this share
#: of it. Two parcels cannot both hold more than half of the same footprint, so the
#: winner is unique by construction and "ambiguous" never needs resolving by preference.
#:
#: The threshold exists because a strict "intersects" test makes almost every building
#: ambiguous: footprints and parcel boundaries come from different sources, so a metre
#: of slop along a shared boundary is normal and would clip a neighbouring parcel. A
#: genuinely straddling building falls below the threshold everywhere and is reported
#: unresolved rather than attached to whichever parcel happened to be read first.
MAJORITY = 0.5

#: Bytes of envelope that follow the 8-byte GeoPackage binary header, indexed by the
#: envelope indicator in flag bits 1-3. Per the OGC GeoPackage spec, table 6.
_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


class LayerMissing(RuntimeError):
    """A layer this import needs is absent from the GeoPackage."""


@dataclass
class ImportReport:
    """What an import did, in terms a reviewer can check against the source file."""

    units: list[Unit] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    reused: int = 0            # units already present, matched by local id
    unresolved: list[str] = field(default_factory=list)   # buildings with no parent
    minted: int = 0            # provisional ULPINs issued

    @property
    def created(self) -> int:
        return len(self.units) - self.reused


def gpkg_geometry(blob: bytes) -> BaseGeometry:
    """Decode a GeoPackage geometry BLOB.

    P2 writes through OGR, so `geom` is not plain WKB: it carries an 8-byte header plus
    an optional envelope. `shapely.wkb.loads` on the raw blob fails with "Unknown WKB
    type" - which is the good case. The bad case is a header whose leading bytes happen
    to parse, so the envelope length is read from the flags rather than assumed.
    """
    if blob[:2] != b"GP":
        # Already plain WKB - our own `unit.footprint_wkb` column, for instance.
        return shapely.wkb.loads(blob)
    flags = blob[3]
    indicator = (flags >> 1) & 0x07
    if indicator not in _ENVELOPE_BYTES:
        raise ValueError(f"invalid GeoPackage envelope indicator {indicator}")
    return shapely.wkb.loads(blob[8 + _ENVELOPE_BYTES[indicator]:])


def _has_layer(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _existing_by_local_id(conn: sqlite3.Connection) -> dict[tuple[str, str], str]:
    """Map (unit_type, local_id) -> unit_id for units a previous import created.

    Import must be repeatable: running it twice over the same file is a normal thing to
    do after P2 adds a layer. `unit_id` is allocated once and never re-derived, so the
    mapping is looked up rather than recomputed - re-deriving it from the local id would
    make identity a function of content, which is exactly what the schema forbids.
    """
    out: dict[tuple[str, str], str] = {}
    import json as _json
    for row in conn.execute("SELECT unit_id, unit_type, attributes FROM unit"):
        attrs = _json.loads(row["attributes"] or "{}")
        local = attrs.get("local_id")
        if local is not None:
            out[(row["unit_type"], str(local))] = row["unit_id"]
    return out


def _provisional(
    conn: sqlite3.Connection,
    unit_id: str,
    parent_ulpin_14: str | None,
    stratum: Stratum,
    level: int,
    settings: ProjectSettings,
) -> str | None:
    """Mint a provisional ULPIN, or None when the parent parcel is unknown.

    Returning None is the point. FR-06 lets the provisional value be recomputed freely,
    but only once there is a real parent to compute it under.
    """
    if not parent_ulpin_14:
        return None
    seq = ledger.allocate_sequence(conn, parent_ulpin_14, stratum.value, level, unit_id)
    version = int(str(settings.ulpin_version).lstrip("vV") or 1)
    return format_ulpin(parent_ulpin_14, version, stratum, level, seq)


#: Columns a re-ingest must never overwrite on a unit it is only refreshing.
#:
#: Ingest reads P2's flat layers, which carry no elevation and no decision, so it builds
#: every unit with `lower_limit=None`, `status=needs_review` and no ULPIN. Written through
#: `save_unit`'s INSERT OR REPLACE, that erased whatever the project had learned since the
#: last import: registering a DEM through the Upload Data screen re-ingested the footprint
#: layer and reset all 910 buildings' derived height ranges to NULL, which surfaced only as
#: a 3D view that had gone empty. The same replace discarded issued ULPINs and reset
#: approved units to needs_review - a land record silently un-approving itself.
#:
#: Re-ingest is a refresh of what the source says, not a reset of what the project knows.
_PRESERVED = (
    "lower_limit", "upper_limit",          # derive's work; ingest has no raster
    "ulpin", "ulpin_version",              # issued at approval and frozen
    "status", "validation_state", "dispute_state",   # decisions, not source facts
    "confidence_score",
)


def _carry_forward(conn: sqlite3.Connection, unit: Unit) -> None:
    """Copy the fields ingest cannot re-derive from the stored row onto `unit`.

    Only for units that already exist. A field the source genuinely restates - geometry,
    source ids, the attributes read off the layer - is left alone and does get refreshed.
    """
    row = conn.execute(
        "SELECT " + ", ".join(_PRESERVED) + " FROM unit WHERE unit_id = ?",
        (unit.unit_id,),
    ).fetchone()
    if row is None:
        return
    for col in _PRESERVED:
        stored = row[col]
        if stored is None:
            continue
        current = getattr(unit, col, None)
        # Enum-valued columns come back as strings; rebuild them through the same type
        # the unit already holds so the record stays typed.
        if hasattr(current, "value") and not isinstance(stored, type(current)):
            stored = type(current)(stored)
        setattr(unit, col, stored)


def import_project(conn: sqlite3.Connection, settings: ProjectSettings) -> ImportReport:
    """Read P2's layers and persist them as units and `contains` relationships.

    `conn` is the project GeoPackage: P2's layers and our tables live in the same file,
    which is what makes the whole project one portable artefact.
    """
    if not _has_layer(conn, "parcel"):
        raise LayerMissing(
            "no `parcel` layer - the ingest block has not written one. There is nothing "
            "to build a cadastre on top of.")

    report = ImportReport()
    known = _existing_by_local_id(conn)
    now = datetime.now(UTC)

    def unit_id_for(kind: str, local_id: str) -> tuple[str, bool]:
        existing = known.get((kind, local_id))
        return (existing, True) if existing else (str(uuid.uuid4()), False)

    # --- parcels ---------------------------------------------------------------
    parcel_cols = _columns(conn, "parcel")
    has_parent_ulpin = "parent_ulpin_14" in parcel_cols
    parcel_geoms: dict[str, BaseGeometry] = {}
    parcel_unit: dict[str, Unit] = {}
    parcel_parent_ulpin: dict[str, str | None] = {}

    for row in conn.execute("SELECT * FROM parcel"):
        local = str(row["parcel_local_id"])
        geom = gpkg_geometry(row["geom"])
        uid, reused = unit_id_for(UnitType.LAND_PARCEL.value, local)
        report.reused += reused
        parent_ulpin = (row["parent_ulpin_14"] or None) if has_parent_ulpin else None

        u = Unit(
            unit_id=uid,
            unit_type=UnitType.LAND_PARCEL,
            status=Status.NEEDS_REVIEW,
            crs=settings.project_crs,
            vertical_datum=settings.vertical_datum,
            footprint_2d=shapely.geometry.mapping(geom),
            source_ids=[str(row["source_id"])],
            created_by=CreatedBy.DERIVED,
            # A parcel's legal column is the project stratum. These are settings, not
            # measurements, so recording them is not a guess about the ground.
            lower_limit=settings.stratum_below_limit_m,
            upper_limit=settings.stratum_above_limit_m,
            recorded_from=now,
            attributes={"local_id": local}
            | ({"parent_ulpin_14": parent_ulpin} if parent_ulpin else {}),
        )
        u.ulpin_provisional = _provisional(
            conn, uid, parent_ulpin, Stratum.SURFACE, 0, settings)
        if u.ulpin_provisional:
            u.ulpin_version = settings.ulpin_version
            report.minted += 1

        parcel_geoms[local] = geom
        parcel_unit[local] = u
        parcel_parent_ulpin[local] = parent_ulpin
        report.units.append(u)

    # --- building footprints ---------------------------------------------------
    if _has_layer(conn, "building_footprint"):
        cols = _columns(conn, "building_footprint")
        for row in conn.execute("SELECT * FROM building_footprint"):
            local = str(row["building_local_id"])
            geom = gpkg_geometry(row["geom"])
            uid, reused = unit_id_for(UnitType.BUILDING.value, local)
            report.reused += reused

            named = str(row["parcel_local_id"]) if (
                "parcel_local_id" in cols and row["parcel_local_id"] is not None) else None
            parent_local, note = _resolve_parcel(local, geom, named, parcel_geoms)
            if parent_local is None:
                report.unresolved.append(local)

            attrs: dict = {"local_id": local}
            if note:
                attrs |= note
            if "floors_count" in cols and row["floors_count"] is not None:
                # Carried through as evidence for `extrude.floors`, which needs a
                # height range before it can act on it. Recording it is not extruding.
                attrs["floor_count"] = int(row["floors_count"])
            # No DEM/DSM arrives through the GeoPackage, so the height range is unknown
            # and stays unknown. FR-03.
            attrs["heights_unavailable"] = "no raster registered for this footprint"

            u = Unit(
                unit_id=uid,
                unit_type=UnitType.BUILDING,
                status=Status.NEEDS_REVIEW,
                crs=settings.project_crs,
                vertical_datum=settings.vertical_datum,
                footprint_2d=shapely.geometry.mapping(geom),
                source_ids=[str(row["source_id"])],
                created_by=CreatedBy.DERIVED,
                lower_limit=None,
                upper_limit=None,
                recorded_from=now,
                attributes=attrs,
            )
            parent_ulpin = parcel_parent_ulpin.get(parent_local) if parent_local else None
            u.ulpin_provisional = _provisional(
                conn, uid, parent_ulpin, Stratum.ABOVE, 0, settings)
            if u.ulpin_provisional:
                u.ulpin_version = settings.ulpin_version
                report.minted += 1
            report.units.append(u)

            if parent_local is not None:
                # Both directions, deliberately. `contains` is what validation walks;
                # `inside` is what a consumer reads to find a unit's parent, and P5's
                # adapter builds lineage from that edge alone. Writing only `contains`
                # left every published building parentless - the record opened on a
                # building with no parcel above it, which is the wrong way round for a
                # land record. `derive` and the fixture have always stored both.
                parcel_uid = parcel_unit[parent_local].unit_id
                report.relationships.append(
                    Relationship(parcel_uid, uid, RelType.CONTAINS, now))
                report.relationships.append(
                    Relationship(uid, parcel_uid, RelType.INSIDE, now))

    # --- utility corridors -----------------------------------------------------
    if _has_layer(conn, "utility_line"):
        for row in conn.execute("SELECT * FROM utility_line"):
            local = str(row["utility_local_id"])
            line = gpkg_geometry(row["geom"])
            width = float(row["corridor_width_m"])
            corridor = line.buffer(width / 2.0, cap_style="flat")
            below = str(row["stratum"]).lower() == "below"
            kind = UnitType.UNDERGROUND_FEATURE if below else UnitType.ELEVATED_STRUCTURE
            uid, reused = unit_id_for(kind.value, local)
            report.reused += reused

            u = Unit(
                unit_id=uid,
                unit_type=kind,
                status=Status.NEEDS_REVIEW,
                crs=settings.project_crs,
                vertical_datum=settings.vertical_datum,
                footprint_2d=shapely.geometry.mapping(corridor),
                source_ids=[str(row["source_id"])],
                created_by=CreatedBy.DERIVED,
                # depth_top_m/depth_bottom_m are signed relative to GROUND, and no DEM
                # has arrived, so they cannot be converted to the project datum. They
                # are carried verbatim and the limits stay unknown rather than being
                # anchored to an assumed ground level.
                lower_limit=None,
                upper_limit=None,
                recorded_from=now,
                attributes={
                    "local_id": local,
                    "easement": True,
                    "utility_kind": row["utility_kind"],
                    "depth_top_m": row["depth_top_m"],
                    "depth_bottom_m": row["depth_bottom_m"],
                    "corridor_width_m": width,
                    "heights_unavailable":
                        "depths are relative to ground; no DEM registered",
                },
            )
            report.units.append(u)

    for u in report.units:
        # A unit whose id was reused already exists; keep what this import cannot know.
        _carry_forward(conn, u)
        save_unit(conn, u)
    for r in report.relationships:
        save_relationship(conn, r)
    conn.commit()
    return report


def _resolve_parcel(
    building_local_id: str,
    footprint: BaseGeometry,
    named_parcel: str | None,
    parcels: dict[str, BaseGeometry],
) -> tuple[str | None, dict]:
    """Which parcel contains this footprint, per the inbound contract.

    An explicit `parcel_local_id` is authoritative - P2 knows something we do not. When
    it names a parcel that is not in the file, that is reported rather than quietly
    replaced with a spatial guess: the mismatch is the interesting fact.
    """
    if named_parcel is not None:
        if named_parcel in parcels:
            return named_parcel, {}
        return None, {"parcel_unresolved":
                      f"names parcel {named_parcel}, which is not in this project"}

    area = footprint.area
    if area <= 0:
        return None, {"parcel_unresolved": "footprint has no area"}

    shares = {
        pid: footprint.intersection(geom).area / area
        for pid, geom in parcels.items()
        if footprint.intersects(geom)
    }
    for pid, share in shares.items():
        if share > MAJORITY:
            return pid, {"parcel_share": round(share, 4)}

    if not shares:
        return None, {"parcel_unresolved": "no parcel overlaps this footprint"}
    best = max(shares.items(), key=lambda kv: kv[1])
    return None, {"parcel_unresolved":
                  f"straddles {len(shares)} parcels, largest share "
                  f"{best[1]:.3f} of {best[0]} - below the {MAJORITY} threshold"}
