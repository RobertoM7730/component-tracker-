"""Shared test setup: every test runs against a throwaway SQLite file so the
real data/components.db is never touched."""

import os
import tempfile

import pytest

# Point the app at a temp DB *before* importing it (db.py reads this at import).
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["TRACKER_DB"] = _DB_PATH

import db          # noqa: E402
import app as app_module  # noqa: E402


@pytest.fixture()
def client():
    # Fresh schema for each test.
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
    db.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def sample_dir():
    return os.path.join(os.path.dirname(__file__), "samples")
