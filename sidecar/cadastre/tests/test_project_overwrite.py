"""Creating a project must never silently destroy one.

Found by running the desktop wizard against a path that already held a project: 5,949
units became 946 and the file went from 7.4 MB to 1.5 MB, with no warning at any step.

This is the one irreversible thing the block can do. An issued ULPIN is a permanent claim
about real property, and the ledger is what proves one was never handed out twice -
deleting the GeoPackage discards both, and no later validation can notice, because there
is nothing left to validate against.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cadastre import project, store
from cadastre.loader import settings_from_dict

SETTINGS = settings_from_dict({
    "project_crs": "EPSG:32643", "vertical_datum": "EGM2008",
    "stratum_below_limit_m": -30.0, "stratum_above_limit_m": 150.0,
    "default_plinth_offset_m": 0.6, "default_parapet_deduction_m": 0.0,
    "ulpin_version": "v1", "ruleset_version": "r1",
})


def _occupied(path: Path, units: int = 3) -> Path:
    """A GeoPackage that already holds units, as a real project would."""
    conn = store.connect(str(path))
    store.init_schema(conn)
    # Approved, and carrying identifiers - which is precisely what makes the loss
    # irreversible. The schema will not let an approved row exist without one.
    for i in range(units):
        conn.execute(
            "INSERT INTO unit (unit_id, unit_type, status, ulpin, ulpin_version, crs, "
            "vertical_datum, footprint_wkb, source_ids, created_by, recorded_from) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"U-{i}", "building", "approved", f"KA05B012345678-V1-A00-{i:03d}-X", "v1",
             "EPSG:32643", "EGM2008", b"x", '["S"]', "human",
             "2026-09-05T00:00:00+00:00"))
    conn.commit()
    conn.close()
    return path


def test_creating_over_an_occupied_project_is_refused(tmp_path):
    """And refused before anything else is validated - see create()'s ordering."""
    gpkg = _occupied(tmp_path / "pilot.gpkg")
    before = gpkg.stat().st_size

    with pytest.raises(project.ProjectExists, match="already holds 3 unit"):
        project.create(gpkg, SETTINGS, [])   # sources never reached

    assert gpkg.exists() and gpkg.stat().st_size == before, "the file was touched anyway"


def test_the_refusal_says_what_would_be_lost(tmp_path):
    """A refusal a person cannot act on is only half a guard."""
    gpkg = _occupied(tmp_path / "pilot.gpkg", units=200)
    with pytest.raises(project.ProjectExists) as err:
        project.create(gpkg, SETTINGS, [])   # sources never reached
    msg = str(err.value)
    assert "200 unit" in msg
    assert "ledger" in msg and "overwrite" in msg


def test_an_empty_or_absent_path_is_not_a_project(tmp_path):
    """Only real loss is protected. A fresh path must not need a flag."""
    assert project._units_held(tmp_path / "nothing.gpkg") == 0

    blank = tmp_path / "blank.gpkg"
    conn = store.connect(str(blank))
    store.init_schema(conn)
    conn.close()
    assert project._units_held(blank) == 0

    (tmp_path / "notours.gpkg").write_bytes(b"not a database")
    assert project._units_held(tmp_path / "notours.gpkg") == 0
