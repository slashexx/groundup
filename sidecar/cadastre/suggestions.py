"""P3 -> P4: AI suggestions in, reviewed volumes out.

The seam FR-05 is about. P3 detects building outlines and estimates storeys; nothing it
produces may become a unit until a person has looked at it. So this module is deliberately
three steps and not one:

    receive()   a batch arrives, is checked against the inbound contract, and is stored
                as *suggestions* - never as units
    review()    a named human accepts, edits or rejects one
    apply()     only `accepted` and `edited` suggestions become building units

Splitting them is the enforcement. A single `import_suggestions()` that created units
would make the human step something a caller could forget, and FR-05 would hold only by
convention. Here there is no code path from `receive` to a unit that does not pass through
a review row carrying somebody's name.

`ai_suggestion` is a table of its own rather than a batch of provisional units, because a
suggestion is not a unit: it has no identity to protect, it can be rejected outright, and
the record of who decided is the evidence the requirement was met.

The rules for attaching a building to a parcel and for minting its provisional identifier
are imported from `ingest_gpkg` rather than restated. A second majority threshold or a
second minting path would be a divergence waiting to happen, and a building the AI found
must be identified exactly like a building P2 delivered.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import shapely.geometry
from jsonschema import Draft202012Validator

from .ingest_gpkg import _provisional, _resolve_parcel
from .models import (
    CreatedBy,
    ModelProvenance,
    ProjectSettings,
    Relationship,
    RelType,
    Representation,
    Status,
    Unit,
    UnitType,
)
from .store import get_unit, save_relationship, save_unit
from .ulpin.encode import Stratum

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "contracts/inbound/p3-suggestion.schema.json"

#: The only two states a suggestion may become a unit from. This *is* FR-05.
CONSUMABLE = frozenset({"accepted", "edited"})
#: States a reviewer may set. `pending` is where a suggestion starts, not somewhere it
#: returns to: a decision that has been made is not un-made by writing it back.
DECISIONS = frozenset({"accepted", "edited", "rejected"})


class ContractViolation(ValueError):
    """A suggestion does not satisfy `contracts/inbound/p3-suggestion.schema.json`."""


class NotReviewed(ValueError):
    """Something tried to turn an unreviewed or rejected suggestion into a unit."""


class AlreadyApplied(ValueError):
    """A suggestion that has already produced a unit cannot be re-decided."""


@dataclass
class ReceiveReport:
    received: int = 0
    stored: int = 0
    already_reviewed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"received": self.received, "stored": self.stored,
                "already_reviewed": self.already_reviewed}


@dataclass
class ApplyReport:
    units: int = 0
    created: int = 0
    reused: int = 0
    minted: int = 0
    with_heights: int = 0
    unresolved: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"units": self.units, "created": self.created, "reused": self.reused,
                "provisional_ulpins": self.minted, "with_heights": self.with_heights,
                "unresolved_suggestions": self.unresolved}


def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))


def check(raw: dict[str, Any], settings: ProjectSettings) -> None:
    """Refuse a suggestion the contract does not describe. Raises `ContractViolation`.

    The CRS check is not pedantry. The schema says the geometry is in the **project** CRS
    in metres - a deliberate deviation from RFC 7946 so that P4 never reprojects per
    operation - and P3 hardcodes `EPSG:32643` as its default. A suggestion carrying some
    other code would be read as metres in the project's own grid and land the building
    hundreds of kilometres from the parcel it belongs to, with nothing to notice: the
    numbers are perfectly plausible, just in the wrong frame.
    """
    errors = sorted(_validator().iter_errors(raw), key=lambda e: e.json_path)
    if errors:
        raise ContractViolation(
            f"{raw.get('suggestion_id', '<no id>')}: "
            + "; ".join(f"{e.json_path} {e.message}" for e in errors[:4]))
    if raw["crs"] != settings.project_crs:
        raise ContractViolation(
            f"{raw['suggestion_id']}: geometry is in {raw['crs']} but this project is "
            f"{settings.project_crs}. Suggestion geometry is in the project CRS by "
            "contract; P4 does not reproject it.")


def receive(conn: sqlite3.Connection, batch: list[dict[str, Any]],
            settings: ProjectSettings) -> ReceiveReport:
    """Store a batch of suggestions. All or nothing.

    Every suggestion is checked before any is written, so a batch carrying one malformed
    entry is refused whole rather than half-imported - a partially applied batch from an
    upstream block is the kind of state nobody thinks to look for.

    A suggestion whose id is already present **and already reviewed is left untouched**.
    Re-running the detector must not quietly erase a decision somebody made; the model
    mints a fresh `suggestion_id` per run, so a repeated id is the same suggestion, not a
    revised one.
    """
    report = ReceiveReport(received=len(batch))
    for raw in batch:
        check(raw, settings)

    now = datetime.now(UTC).isoformat()
    for raw in batch:
        sid = raw["suggestion_id"]
        row = conn.execute(
            "SELECT review_state FROM ai_suggestion WHERE suggestion_id = ?", (sid,)
        ).fetchone()
        if row is not None and row[0] != "pending":
            report.already_reviewed.append(sid)
            continue
        attrs = raw.get("attributes") or {}
        conn.execute(
            "INSERT OR REPLACE INTO ai_suggestion (suggestion_id, kind, geometry, crs, "
            "source_raster_ids, confidence, model_name, model_version, model_run_at, "
            "attributes, review_state, reviewed_by, reviewed_at, edited_geometry, "
            "unit_id, received_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,?)",
            (sid, raw["kind"], json.dumps(raw["geometry"]), raw["crs"],
             json.dumps(raw["source_raster_ids"]), float(raw["confidence"]),
             raw["model"]["name"], raw["model"]["version"], raw["model"]["run_at"],
             json.dumps(attrs), "pending", now))
        report.stored += 1
    conn.commit()
    return report


def review(conn: sqlite3.Connection, suggestion_id: str, state: str, actor: str,
           edited_geometry: dict[str, Any] | None = None) -> None:
    """Record a human decision. This is the step FR-05 exists to require.

    `edited` demands a geometry, because that is the only thing that distinguishes it
    from `accepted`; the database enforces the same rule, so the invariant survives a
    caller that bypasses this function.

    A suggestion that has already produced a unit is refused. The unit has a lifecycle of
    its own from that point - `needs_review` to approved or back to draft - and rewinding
    the suggestion behind it would mean either orphaning a unit or deleting an allocated
    identity, which the ledger forbids.
    """
    if state not in DECISIONS:
        raise ValueError(f"{state!r} is not a decision; expected one of {sorted(DECISIONS)}")
    if not actor:
        raise ValueError("a review must name the person who made it")
    row = conn.execute(
        "SELECT unit_id FROM ai_suggestion WHERE suggestion_id = ?", (suggestion_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"no suggestion {suggestion_id}")
    if row[0] is not None:
        raise AlreadyApplied(
            f"{suggestion_id} has already become unit {row[0]}. Act on the unit instead: "
            "an issued identity is never withdrawn.")
    if state == "edited" and not edited_geometry:
        raise ValueError(
            "an edited suggestion must carry the corrected geometry; without it there is "
            "nothing to distinguish the edit from an acceptance")

    conn.execute(
        "UPDATE ai_suggestion SET review_state = ?, reviewed_by = ?, reviewed_at = ?, "
        "edited_geometry = ? WHERE suggestion_id = ?",
        (state, actor, datetime.now(UTC).isoformat(),
         json.dumps(edited_geometry) if edited_geometry else None, suggestion_id))
    conn.commit()


def listing(conn: sqlite3.Connection, state: str | None = None) -> list[dict[str, Any]]:
    """Suggestions as a reviewer sees them, newest model run first."""
    sql = ("SELECT suggestion_id, kind, geometry, crs, source_raster_ids, confidence, "
           "model_name, model_version, model_run_at, attributes, review_state, "
           "reviewed_by, reviewed_at, edited_geometry, unit_id FROM ai_suggestion")
    args: tuple = ()
    if state is not None:
        sql += " WHERE review_state = ?"
        args = (state,)
    sql += " ORDER BY model_run_at DESC, suggestion_id"
    out = []
    for r in conn.execute(sql, args):
        out.append({
            "suggestion_id": r["suggestion_id"], "kind": r["kind"],
            "geometry": json.loads(r["geometry"]), "crs": r["crs"],
            "source_raster_ids": json.loads(r["source_raster_ids"]),
            "confidence": r["confidence"],
            "model": {"name": r["model_name"], "version": r["model_version"],
                      "run_at": r["model_run_at"]},
            "attributes": json.loads(r["attributes"]),
            "review": {"state": r["review_state"], "reviewed_by": r["reviewed_by"],
                       "reviewed_at": r["reviewed_at"],
                       "edited_geometry": json.loads(r["edited_geometry"])
                       if r["edited_geometry"] else None},
            "unit_id": r["unit_id"],
        })
    return out


def geometry_of(row: sqlite3.Row) -> dict[str, Any]:
    """The outline P4 must use: the reviewer's, when there is one.

    The contract is explicit that `edited_geometry` supersedes `geometry`. Reading the
    model's original outline for an edited suggestion would silently discard the one
    correction a human actually made.
    """
    if row["review_state"] == "edited":
        return json.loads(row["edited_geometry"])
    return json.loads(row["geometry"])


def apply(conn: sqlite3.Connection, settings: ProjectSettings) -> ApplyReport:
    """Turn reviewed suggestions into building units.

    Only `accepted` and `edited`. Everything else is skipped without comment because
    skipping is the correct behaviour, not an error: `pending` means nobody has looked
    yet and `rejected` means somebody looked and said no.

    Repeatable, like ingest: the unit a suggestion produced is remembered on the
    suggestion row, so applying twice refreshes that unit rather than minting a second
    identity for the same building.
    """
    report = ApplyReport()
    parcels = _parcel_geometries(conn)
    now = datetime.now(UTC)

    rows = conn.execute(
        "SELECT * FROM ai_suggestion WHERE review_state IN ('accepted', 'edited') "
        "ORDER BY suggestion_id").fetchall()
    for row in rows:
        geom = shapely.geometry.shape(geometry_of(row))
        uid = row["unit_id"] or str(uuid.uuid4())
        report.reused += 1 if row["unit_id"] else 0

        parent_uid, note = _resolve_parcel(row["suggestion_id"], geom, None,
                                           {p: g for p, (g, _) in parcels.items()})
        if parent_uid is None:
            report.unresolved.append(row["suggestion_id"])

        unit = _unit_from(row, geom, uid, settings, note, now,
                          _source_ids(conn, json.loads(row["source_raster_ids"])))
        if unit.lower_limit is not None:
            report.with_heights += 1

        parent_ulpin = parcels[parent_uid][1] if parent_uid else None
        if parent_ulpin:
            unit.attributes = unit.attributes | {"parent_ulpin_14": parent_ulpin}
        unit.ulpin_provisional = _provisional(
            conn, uid, parent_ulpin, Stratum.ABOVE, 0, settings)
        if unit.ulpin_provisional:
            unit.ulpin_version = settings.ulpin_version
            report.minted += 1

        save_unit(conn, unit)
        conn.execute("UPDATE ai_suggestion SET unit_id = ? WHERE suggestion_id = ?",
                     (uid, row["suggestion_id"]))
        report.units += 1

        if parent_uid is not None:
            # Both directions, as everywhere else: validation walks `contains`, and a
            # consumer finds a unit's parent through `inside`.
            save_relationship(conn, Relationship(parent_uid, uid, RelType.CONTAINS, now))
            save_relationship(conn, Relationship(uid, parent_uid, RelType.INSIDE, now))

    report.created = report.units - report.reused
    conn.commit()
    return report


def apply_one(conn: sqlite3.Connection, suggestion_id: str,
              settings: ProjectSettings) -> str:
    """Apply a single suggestion, refusing one nobody has accepted.

    `apply()` filters silently, which is right for a batch. Asked about one suggestion by
    name, silence would be the wrong answer: the caller believes this one is ready.
    """
    row = conn.execute("SELECT review_state FROM ai_suggestion WHERE suggestion_id = ?",
                       (suggestion_id,)).fetchone()
    if row is None:
        raise KeyError(f"no suggestion {suggestion_id}")
    if row[0] not in CONSUMABLE:
        raise NotReviewed(
            f"{suggestion_id} is {row[0]}. Only an accepted or edited suggestion becomes "
            "a unit - an AI outline never enters the register without a human (FR-05).")
    apply(conn, settings)
    return conn.execute("SELECT unit_id FROM ai_suggestion WHERE suggestion_id = ?",
                        (suggestion_id,)).fetchone()[0]


def _source_ids(conn: sqlite3.Connection, raster_ids: list[str]) -> list[str]:
    """Translate P3's raster ids into the source registry entries behind them.

    The contract hands us `source_raster_ids` - identifiers in P2's `raster` table - but
    `Unit.source_ids` references `source`, which is where accuracy lives. Storing raster
    ids there produces a unit whose provenance resolves to nothing, so no comparison
    tolerance can be derived for it and every overlap involving it is judged against a
    default rather than against what the data is actually worth. It shows up as
    PROVENANCE_MISSING, which is the correct complaint about the wrong cause.

    A raster we have no registry entry for is carried through verbatim rather than
    dropped or invented: PROVENANCE_MISSING then fires for the real reason.
    """
    try:
        rows = conn.execute("SELECT raster_id, source_id FROM raster").fetchall()
    except sqlite3.OperationalError:
        return list(raster_ids)
    by_raster = {r["raster_id"]: r["source_id"] for r in rows}
    out: list[str] = []
    for rid in raster_ids:
        resolved = by_raster.get(rid) or rid
        if resolved not in out:
            out.append(resolved)
    return out


def _parcel_geometries(conn: sqlite3.Connection) -> dict:
    """Every parcel's footprint and parent ULPIN, keyed by `unit_id`."""
    out = {}
    for r in conn.execute("SELECT unit_id FROM unit WHERE unit_type = ?",
                          (UnitType.LAND_PARCEL.value,)):
        parcel = get_unit(conn, r["unit_id"])
        if parcel is None:
            continue
        out[parcel.unit_id] = (shapely.geometry.shape(parcel.footprint_2d),
                               parcel.attributes.get("parent_ulpin_14"))
    return out


def _unit_from(row: sqlite3.Row, geom, uid: str, settings: ProjectSettings,
               note: dict, now: datetime, source_ids: list[str]) -> Unit:
    """One accepted suggestion as a building unit.

    Heights follow `extrude.building.build` exactly - base is ground plus the project's
    plinth offset, top is the roof level - so a building the model found and a building
    the rasters produced mean the same thing. They are set only when the suggestion
    carries *both* levels; one without the other is not half a height, it is no height,
    and FR-03 says so rather than filling the gap.

    `created_by` is `ai` and the confidence and model provenance are carried through. That
    is what makes the CONFIDENCE_LOW rule live: it has always been written to fire on
    AI-created units and until now no such unit existed.
    """
    attrs = json.loads(row["attributes"])
    ground = attrs.get("ground_level_m")
    roof = attrs.get("roof_level_m")

    unit_attrs: dict[str, Any] = {
        "suggestion_id": row["suggestion_id"],
        # Kept because the source registry entry is shared between rasters, so the unit's
        # own `source_ids` no longer say which surface it was measured from.
        "source_raster_ids": json.loads(row["source_raster_ids"]),
    } | note
    for key in ("floor_count", "floor_count_method"):
        if attrs.get(key) is not None:
            unit_attrs[key] = attrs[key]

    if ground is not None and roof is not None:
        base = ground + settings.default_plinth_offset_m
        top = roof
        unit_attrs |= {"ground_level_m": ground, "roof_level_m": roof,
                       "plinth_offset_m": settings.default_plinth_offset_m}
    else:
        base = top = None
        unit_attrs["heights_unavailable"] = (
            "the suggestion carried no ground and roof level")

    return Unit(
        unit_id=uid,
        unit_type=UnitType.BUILDING,
        status=Status.NEEDS_REVIEW,
        crs=row["crs"],
        vertical_datum=settings.vertical_datum,
        footprint_2d=geom.__geo_interface__,
        source_ids=source_ids,
        created_by=CreatedBy.AI,
        representation=Representation.PRISM,
        lower_limit=base,
        upper_limit=top,
        confidence_score=row["confidence"],
        model=ModelProvenance(row["model_name"], row["model_version"],
                              datetime.fromisoformat(row["model_run_at"])),
        recorded_from=now,
        attributes=unit_attrs,
    )
