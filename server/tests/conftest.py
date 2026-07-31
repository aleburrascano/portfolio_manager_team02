"""
Shared fixtures for the server test suite.

The app is a module-level singleton (see app.py), so DATABASE_URL has to be
pointed at an in-memory SQLite database before `app` is ever imported - that
happens here, at collection time, before any test module runs. Tables are
created automatically by db.connection.init_db() for that URL, so there's no
migration to run. Each test gets a clean database via the autouse
`_clean_tables` fixture rather than a fresh app, since the engine/session
machinery is process-wide.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ.setdefault('CORS_ORIGINS', 'http://localhost:5173')

import pytest

import app as app_module
from db.connection import get_engine
from db.models import Base


@pytest.fixture()
def app():
    app_module.app.config['TESTING'] = True
    return app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Empty every table after each test so tests don't see each other's rows."""
    yield
    engine = get_engine()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
