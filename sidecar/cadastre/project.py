"""Create a project from the operator's own data — the wizard's backend.

Everything else in this block consumes a GeoPackage that already exists. Something has
to make one, and until now that was `tools/run_chain.py` over P2's sample files: fine for
a rehearsal, useless to an operator with a ward of their own. This is the same sequence
the chain runs, reachable from P1.

**Source accuracy is required, not defaulted.** `contracts/inbound/p2-geopackage.md` is
explicit that `horizontal_accuracy_m` and `vertical_accuracy_m` drive every geometric
tolerance P4 computes (`tol = k * sqrt(acc_a^2 + acc_b^2)`), and that a writer supplying
an optimistic default makes every source silently claim survey grade. P2's
`process_file` does default them to 0.20/0.25 m. We refuse instead: pydantic marks both
mandatory, so a caller that omits them gets a 422 naming the field rather than a project
whose tolerances are fiction. Under-claiming accuracy is safe; over-claiming fills the
review queue with false positives until reviewers stop reading it.

`default_parapet_deduction_m` is likewise refused if non-zero — the roof estimator is a
median and returns the slab directly, so a deduction on top lowers every floor and
*every validation rule still passes*. `extrude.building` raises `EstimatorMismatch` on
it, but only at derive time; the API route repeats the check at creation so the operator
hears it while the field is still in front of them. `loader.settings_from_dict` does not
check it and never did — it maps keys and nothing more.
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

#: P2 lives beside us in the sidecar, not on PyPI.
_INGEST = Path(__file__).resolve().parents[1] / "ingest"
if str(_INGEST) not in sys.path:
    sys.path.insert(0, str(_INGEST))

#: Vector source types and the contract layer each one lands in. A source type absent
#: here carries no geometry P4 can read as a unit (imagery, point clouds, survey
#: control) and is registered as provenance only - see `REGISTER_ONLY`.
VECTOR_LAYERS = {
    "parcel_map": "parcel",
    "footprint": "building_footprint",
    "utility": "utility_line",
}

#: Raster source types and their `raster.kind`. These are registered, not harmonized:
#: `derive` reads them off disk when it needs ground and roof levels.
RASTER_KINDS = {"dem": "DEM", "dsm": "DSM", "ortho": "ORTHO"}

#: Accepted but geometry-free: recorded in `source` so a unit built from them can name
#: its provenance, with nothing for P2 to reproject. `pointcloud` is here rather than in
#: RASTER_KINDS because a LAS/LAZ tile is not a raster and P4 reads a DEM/DSM derived
#: from it, never the tile itself.
REGISTER_ONLY = {"pointcloud", "floorplan", "survey_control"}

SOURCE_TYPES = set(VECTOR_LAYERS) | set(RASTER_KINDS) | REGISTER_ONLY


class ProjectExists(RuntimeError):
    """A project already lives at this path and creating over it would destroy it.

    Overwriting is not merely losing work. An issued ULPIN is a permanent claim about
    real property, and the ledger is what proves one was never handed out twice; deleting
    the file discards both. This is the one irreversible thing this block can do, so it
    does not happen by default and never happens silently.
    """


class ProjectCreateError(Exception):
    """The project could not be built. Carries a message meant for the operator."""


@dataclass
class CreatedProject:
    db_path: str
    sources: list[str] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    rasters: list[str] = field(default_factory=list)
    registered_only: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _register_source(conn: sqlite3.Connection, s, coverage_wkt: str = "") -> None:
    """Write one row of the `source` registry — the table P4's tolerances come from."""
    conn.execute(
        "INSERT OR REPLACE INTO source (source_id, source_type, name, provider, "
        "capture_date, crs, vertical_datum, horizontal_accuracy_m, vertical_accuracy_m, "
        "coverage_wkt, processing_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (s.source_id, s.source_type, s.name, s.provider, s.capture_date, s.crs,
         s.vertical_datum, s.horizontal_accuracy_m, s.vertical_accuracy_m,
         coverage_wkt, s.processing_status),
    )


def create(gpkg: Path, settings, sources: list, *,
           overwrite: bool = False) -> CreatedProject:
    """Build a project GeoPackage from `settings` and the operator's `sources`.

    Vector sources go through P2's harmonizer so everything lands in the project CRS in
    metres. Rasters and geometry-free sources are registered where they sit; copying a
    12 GB point cloud into the project folder to satisfy tidiness is not worth the wait,
    and `raster.path` exists precisely to point at one.
    """
    from run_pipeline import GeoDataPipeline  # P2, resolved via sys.path above


    # Asked before anything else, including whether the sources exist. A caller with a
    # typo in a source path should be told about the typo; a caller whose paths are all
    # valid should not have their existing project deleted on the way to finding out.
    if not overwrite:
        held = _units_held(gpkg)
        if held:
            raise ProjectExists(
                f"{gpkg} already holds {held} unit(s). Creating a project here would "
                "delete them, along with every identifier they have been issued and the "
                "ledger proving those were never reused. Choose another path, or pass "
                "overwrite explicitly, having decided that is what you want.")

    if not sources:
        raise ProjectCreateError(
            "a project needs at least one source. Add a parcel map to begin: it is the "
            "only layer that carries the parent ULPIN every other unit inherits.")

    missing = [s.path for s in sources if not Path(s.path).exists()]
    if missing:
        raise ProjectCreateError("file not found: " + ", ".join(missing))

    gpkg.parent.mkdir(parents=True, exist_ok=True)
    gpkg.unlink(missing_ok=True)

    pipeline = GeoDataPipeline(gpkg_output_path=str(gpkg), target_crs=settings.project_crs)
    pipeline.setup_project()
    out = CreatedProject(db_path=str(gpkg))

    # Vectors first: the GeoPackage does not exist as a file until a layer is written,
    # and `ensure_contract_tables` returns early on a path that is not there yet.
    for s in (x for x in sources if x.source_type in VECTOR_LAYERS):
        layer = VECTOR_LAYERS[s.source_type]
        ok = pipeline.process_file(
            s.path, layer, s.source_id, s.source_type,
            source_name=s.name,
            horizontal_accuracy_m=s.horizontal_accuracy_m,
            vertical_accuracy_m=s.vertical_accuracy_m,
        )
        if not ok:
            raise ProjectCreateError(
                f"P2 could not read {Path(s.path).name} as a {layer} layer. Check that it "
                "is a vector file with a CRS its driver can report.")
        out.sources.append(s.source_id)
        out.layers.append(layer)

    if not gpkg.exists():
        raise ProjectCreateError(
            "no vector layer was written, so there is no project file. At least one "
            "parcel map or building footprint source is required; rasters and floor "
            "plans are registered against a project, they cannot create one.")

    conn = sqlite3.connect(gpkg)
    try:
        # P2 stamps its own defaults when it writes the first layer; the operator's
        # settings are what the project actually runs on, so they are written last.
        conn.execute(
            "INSERT OR REPLACE INTO project_settings (id, project_crs, vertical_datum, "
            "stratum_below_limit_m, stratum_above_limit_m, default_plinth_offset_m, "
            "default_parapet_deduction_m, ulpin_version, ruleset_version) "
            "VALUES (1,?,?,?,?,?,?,?,?)",
            (settings.project_crs, settings.vertical_datum,
             settings.stratum_below_limit_m, settings.stratum_above_limit_m,
             settings.default_plinth_offset_m, settings.default_parapet_deduction_m,
             settings.ulpin_version, settings.ruleset_version))

        for s in sources:
            if s.source_type in VECTOR_LAYERS:
                continue
            _register_source(conn, s)
            out.sources.append(s.source_id)
            if s.source_type in RASTER_KINDS:
                conn.execute(
                    "INSERT OR REPLACE INTO raster (raster_id, kind, path, crs, "
                    "vertical_datum, resolution_m, source_id) VALUES (?,?,?,?,?,?,?)",
                    (f"RST-{s.source_id}", RASTER_KINDS[s.source_type], s.path, s.crs,
                     s.vertical_datum, s.resolution_m or s.horizontal_accuracy_m,
                     s.source_id))
                out.rasters.append(s.source_id)
            else:
                out.registered_only.append(s.source_id)
        conn.commit()
    finally:
        conn.close()

    return out


def new_source_id(source_type: str) -> str:
    """A readable, unique source id. Readable because it shows up in every finding."""
    return f"SRC-{source_type.upper().replace('_', '-')}-{uuid.uuid4().hex[:6]}"


class UnreadableDestination(RuntimeError):
    """Something is at the destination path and we could not read it.

    Distinct from `ProjectExists`, which means we read it and it holds units. Here we do
    not know what it holds, which is the case where deleting it is least defensible.
    """


def _units_held(gpkg: Path) -> int:
    """How many units an existing GeoPackage already holds, 0 if it holds none.

    Absent means zero: there is nothing there to destroy.

    A file we cannot read is NOT zero. This previously returned 0 on any `sqlite3.Error`
    and reasoned that a path which is "unreadable, or not one of our projects" is not
    something we would be destroying - exactly backwards. A locked database, a corrupt
    file, a GeoPackage written by QGIS holding a year of survey work, or one belonging to
    another tool all raise here, and every one of them was then deleted by the
    `unlink(missing_ok=True)` two lines after the guard. The only operation in this module
    that cannot be undone was reachable by any read failure.

    Not being able to read the destination is a reason to stop, not to proceed.
    """
    if not gpkg.exists():
        return 0
    try:
        conn = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
        try:
            return int(conn.execute("SELECT count(*) FROM unit").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.OperationalError as err:
        # "no such table: unit" is the one readable answer that genuinely means empty:
        # the file opened as SQLite and simply is not one of our projects yet.
        if "no such table" in str(err).lower():
            return 0
        raise UnreadableDestination(
            f"{gpkg} exists and could not be read: {err}. Refusing to overwrite a file "
            "whose contents are unknown. Move it aside, or choose another path."
        ) from err
    except sqlite3.Error as err:
        raise UnreadableDestination(
            f"{gpkg} exists and is not a readable database: {err}. Refusing to overwrite "
            "a file whose contents are unknown. Move it aside, or choose another path."
        ) from err


def add_sources(gpkg: Path, settings, sources: list) -> CreatedProject:
    """Add sources to a project that already exists.

    Creation and addition are the same work in a different order: `create` writes the
    project settings first because nothing has stamped them yet, and this reads them back
    because the operator set them once and every unit already carries them. Letting a
    later upload restate the CRS would let two halves of one project disagree about where
    they are.

    Nothing is deleted. The GeoPackage is opened, a layer is appended, and the caller
    re-ingests - so adding a footprint layer to a project that already holds its parcels
    keeps the parcels, and their identifiers with them.
    """
    from run_pipeline import GeoDataPipeline

    if not gpkg.exists():
        raise ProjectCreateError(
            f"{gpkg} does not exist. Create the project before adding to it.")
    if not sources:
        raise ProjectCreateError("no sources to add.")

    missing = [s.path for s in sources if not Path(s.path).exists()]
    if missing:
        raise ProjectCreateError("file not found: " + ", ".join(missing))

    out = CreatedProject(db_path=str(gpkg))
    pipeline = GeoDataPipeline(gpkg_output_path=str(gpkg), target_crs=settings.project_crs)

    for s in (x for x in sources if x.source_type in VECTOR_LAYERS):
        layer = VECTOR_LAYERS[s.source_type]
        ok = pipeline.process_file(
            s.path, layer, s.source_id, s.source_type,
            source_name=s.name,
            horizontal_accuracy_m=s.horizontal_accuracy_m,
            vertical_accuracy_m=s.vertical_accuracy_m,
        )
        if not ok:
            raise ProjectCreateError(
                f"P2 could not read {Path(s.path).name} as a {layer} layer. Check that it "
                "is a vector file with a CRS its driver can report.")
        out.sources.append(s.source_id)
        out.layers.append(layer)

    conn = sqlite3.connect(gpkg)
    try:
        for s in sources:
            if s.source_type in VECTOR_LAYERS:
                continue
            _register_source(conn, s)
            out.sources.append(s.source_id)
            if s.source_type in RASTER_KINDS:
                conn.execute(
                    "INSERT OR REPLACE INTO raster (raster_id, kind, path, crs, "
                    "vertical_datum, resolution_m, source_id) VALUES (?,?,?,?,?,?,?)",
                    (f"RST-{s.source_id}", RASTER_KINDS[s.source_type], s.path, s.crs,
                     s.vertical_datum, s.resolution_m or s.horizontal_accuracy_m,
                     s.source_id))
                out.rasters.append(s.source_id)
            else:
                out.registered_only.append(s.source_id)
        conn.commit()
    finally:
        conn.close()

    return out
