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
os.environ.setdefault('START_LIMIT_ORDER_POLLER', 'false')

import pytest

import app as app_module
import services.bond_pricing as bond_pricing
import services.market_data as market_data
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


@pytest.fixture(autouse=True)
def _clear_market_data_cache():
    """
    Drop cached market data around every test.

    The caches are process-wide and outlive a test the way the engine does,
    so without this a stubbed price set by one test would still be answering
    in the next one - and a test that stubs the feed after a real lookup has
    already been cached would never see its own stub.
    """
    market_data.clear_caches()
    bond_pricing.clear_cache()
    yield
    market_data.clear_caches()
    bond_pricing.clear_cache()
