"""A guard that fires correctly still owes the caller a readable answer.

Several routes reach a database that is not a project, or an identifier space that is
full. Uncaught, each became a 500 with a stack trace - which reads as "the server is
broken" rather than "this file is not a project" or "this parcel has no numbers left".
The operator's next action is completely different in each case, and a 500 names none
of them.

These are registered on the app, not on individual handlers, so a route added later
inherits them. Tests go through the app for that reason.
"""

from __future__ import annotations

import sqlite3

import pytest
from cadastre.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_a_path_that_is_not_a_database_is_refused_readably(client, tmp_path):
    junk = tmp_path / "notes.txt"
    junk.write_text("this is not a geopackage")
    r = client.get("/cadastre/document", params={"db_path": str(junk)})
    assert r.status_code == 422, r.text
    assert "not a readable database" in r.text or "not a cadastre project" in r.text


def test_a_sqlite_file_that_is_not_a_project_names_what_is_missing(client, tmp_path):
    other = tmp_path / "other.gpkg"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()

    r = client.get("/cadastre/runs/latest", params={"db_path": str(other)})
    assert r.status_code == 422, r.text
    assert "not a cadastre project" in r.text or "no such table" in r.text.lower()


def test_a_missing_project_path_is_refused_rather_than_creating_a_stray_file(client, tmp_path):
    """`sqlite3.connect` creates the file it is given, so a default was a landmine."""
    before = set(tmp_path.iterdir())
    assert client.get("/cadastre/document").status_code == 422
    assert set(tmp_path.iterdir()) == before


def test_an_absent_file_is_not_silently_created_as_an_empty_project(client, tmp_path):
    absent = tmp_path / "never-made.gpkg"
    r = client.get("/cadastre/document", params={"db_path": str(absent)})
    assert r.status_code == 422, r.text
    # It may be touched by sqlite3.connect, but it must never look like a real project.
    assert not absent.exists() or absent.stat().st_size == 0
