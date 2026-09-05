"""Registered rasters -> AI suggestions in the review queue.

The sibling of `derive.py`, and the same shape of seam: `derive` knows where a project's
rasters live and turns them into heights, this one turns them into candidate buildings.
P3 takes numpy arrays and knows nothing about a project; something has to read the raster
registry, open the surfaces and hand them over, and that is not P3's job.

It exists because **P1 speaks only HTTP.** `desktop/src-tauri/tauri.conf.json` declares no
`externalBin` and spawns no process, so the desktop shell reaches this block through
`http://127.0.0.1:8000` and nothing else. Without a route the review queue could only ever
be filled by a command-line tool, and the AI screen would have nothing to call. P3's own
`main()` prints three lines and runs no detection; giving it a working CLI would not help,
because no part of the product would invoke it.

Nothing here decides anything. Detection fills the queue; `suggestions.py` is where a
human accepts, corrects or rejects, and only then does a unit exist.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Protocol

import shapely.geometry
import shapely.wkb

from . import suggestions
from .ingest_gpkg import MAJORITY
from .models import ProjectSettings, UnitType

#: What `sidecar/ai` needs installed. Declared in its `pyproject.toml`, but nothing
#: installs it into the shared venv, so the failure has to name the fix.
P3_INSTALL = "./.venv/bin/pip install opencv-python-headless onnxruntime"


class AIUnavailable(RuntimeError):
    """P3 is not installed in this environment."""


class Detector(Protocol):
    """P3's nDSM path, as this module needs it.

    Narrow on purpose: a callable taking two surfaces and the georeferencing that relates
    them to the ground, returning contract-shaped suggestions. Everything about *how* the
    detection happens stays behind it, which is what lets the tests below assert the one
    thing that actually goes wrong at this seam - whether the transform was passed - with
    no model, no onnxruntime and no opencv.
    """

    def __call__(self, dsm, dem, raster_ids: list[str], crs: str,
                 transform) -> list[dict[str, Any]]: ...


@dataclass
class DetectReport:
    dem_raster_id: str | None = None
    dsm_raster_id: str | None = None
    found: int = 0
    stored: int = 0
    already_reviewed: list[str] = field(default_factory=list)
    #: Suggestions already in the project that this run found again, by their existing id.
    rediscovered: list[str] = field(default_factory=list)
    #: Detections matching a building the project already holds. Not offered for review:
    #: the question is settled, and a queue full of settled questions is one nobody reads.
    already_mapped: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dem_raster_id": self.dem_raster_id, "dsm_raster_id": self.dsm_raster_id,
            "found": self.found, "stored": self.stored,
            "already_reviewed": self.already_reviewed,
            "rediscovered": self.rediscovered,
            "already_mapped": self.already_mapped,
        }


def already_mapped(conn: sqlite3.Connection, geom) -> str | None:
    """The building unit already in this project that `geom` is another sighting of.

    `_rediscovery` compares a detection against other *suggestions*, which stops pressing
    the button twice from stacking outlines but cannot see the register. On the Trivandrum
    pilot that gap showed plainly: 910 buildings imported from footprints, then detect
    returned 727 suggestions of which every single one overlapped an existing building,
    with `rediscovered` empty throughout.

    A queue of 727 items that are all already mapped is worse than an empty one - it is a
    reviewer being asked 727 times about work that is done, which is how people learn to
    click past a queue without reading it.

    Same test as `_rediscovery`, and deliberately the same threshold: each footprint more
    than half inside the other, symmetric, so a large detection cannot swallow a small
    building or the reverse.
    """
    for row in conn.execute(
        "SELECT unit_id, footprint_wkb FROM unit WHERE unit_type = ?",
        (UnitType.BUILDING.value,),
    ):
        other = shapely.wkb.loads(row["footprint_wkb"])
        if geom.area <= 0 or other.area <= 0:
            continue
        shared = geom.intersection(other).area
        if shared > MAJORITY * geom.area and shared > MAJORITY * other.area:
            return row["unit_id"]
    return None


def _rediscovery(conn: sqlite3.Connection, geom) -> str | None:
    """The suggestion already in this project that `geom` is another sighting of.

    Detection is a button, and P3 mints a fresh `suggestion_id` every run, so pressing it
    twice stacked a second identical outline behind the first - including behind one
    somebody had already rejected, which is the queue quietly re-asking a settled
    question. The id guard in `suggestions.receive` cannot see this: the ids genuinely
    differ. Found by calling POST /cadastre/detect twice.

    Same building means **each footprint is more than half inside the other**. Symmetric,
    so a large detection cannot swallow a small one or the reverse, and the threshold is
    `ingest_gpkg.MAJORITY` rather than a second number invented here - it already answers
    "is this the same piece of ground" for parcel attachment, and a project carrying two
    thresholds for one question eventually disagrees with itself.

    An edited suggestion is compared on the geometry the reviewer corrected it to, which
    is the outline the project actually holds.
    """
    for row in conn.execute("SELECT * FROM ai_suggestion"):
        other = shapely.geometry.shape(suggestions.geometry_of(row))
        if geom.area <= 0 or other.area <= 0:
            continue
        shared = geom.intersection(other).area
        if shared > MAJORITY * geom.area and shared > MAJORITY * other.area:
            return row["suggestion_id"]
    return None


def p3_detector() -> Detector:
    """P3's `process_ndsm_detection`, wrapped so the transform cannot be forgotten.

    Passing the raster's affine transform is not optional even though the parameter is.
    Without it P3 falls back to the identity and returns polygons in *pixel indices*,
    which are plain floats indistinguishable from metres: a building at (50, 50) in
    UTM 43N lands about 276 km from its parcel, in the sea, and every check downstream
    runs happily on it. See `blocks/p3-ai.md`.
    """
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    for sub in ("sidecar/ai", "sidecar/ai/src"):
        path = str(repo / sub)
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        from ai.ndsm_estimator import NDSMEstimator
        from run_detection import process_ndsm_detection
    except ModuleNotFoundError as err:
        raise AIUnavailable(
            f"the AI block is not installed here ({err.name} is missing). It is a "
            f"declared dependency of sidecar/ai:\n  {P3_INSTALL}") from err

    def detect(dsm, dem, raster_ids, crs, transform):
        ndsm = NDSMEstimator().compute_ndsm(dsm, dem)
        return process_ndsm_detection(ndsm, dsm, dem, raster_ids, crs=crs,
                                      transform=transform)

    return detect


def run(conn: sqlite3.Connection, settings: ProjectSettings, *,
        detector: Detector | None = None) -> DetectReport:
    """Detect buildings on the project's registered surfaces and queue what is found.

    Detecting and queueing are one call because a detection whose results are not stored
    is of no use to a review screen, and `suggestions.receive` is the contract gate every
    suggestion has to pass anyway.

    A project with no DEM/DSM registered is reported, not refused: there is simply nothing
    to look at, which is the same answer `derive` gives and the same reason.
    """
    from .derive import _rasters

    report = DetectReport()
    registry = _rasters(conn)
    dem_rows, dsm_rows = registry.get("DEM", []), registry.get("DSM", [])
    if not dem_rows or not dsm_rows:
        return report
    report.dem_raster_id = dem_rows[0]["raster_id"]
    report.dsm_raster_id = dsm_rows[0]["raster_id"]

    import rasterio

    with rasterio.open(dem_rows[0]["path"]) as dem_src, \
         rasterio.open(dsm_rows[0]["path"]) as dsm_src:
        dem, dsm = dem_src.read(1), dsm_src.read(1)
        transform = dsm_src.transform

    found = (detector or p3_detector())(
        dsm, dem, [report.dsm_raster_id, report.dem_raster_id],
        settings.project_crs, transform)
    report.found = len(found)

    fresh = []
    for raw in found:
        geom = shapely.geometry.shape(raw["geometry"])

        # Asked before the suggestion-level check: a building already in the register is
        # settled, and re-offering it is not a duplicate question but a pointless one.
        mapped = already_mapped(conn, geom)
        if mapped is not None:
            report.already_mapped.append(mapped)
            continue

        seen = _rediscovery(conn, geom)
        if seen is not None:
            report.rediscovered.append(seen)
            continue
        fresh.append(raw)

    got = suggestions.receive(conn, fresh, settings)
    report.stored = got.stored
    report.already_reviewed = got.already_reviewed
    return report
