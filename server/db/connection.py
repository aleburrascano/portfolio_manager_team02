"""
SQLAlchemy engine and request-scoped session.

Which database is used is decided entirely by DATABASE_URL, so the same
code runs against MySQL in production and SQLite (a file, or in-memory) in
development. If DATABASE_URL isn't set the URL is assembled from the
existing DB_* variables, so setups predating this migration keep working.
"""
import os
from typing import Optional
from urllib.parse import quote_plus

from flask import Flask, g
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, User

_engine: Optional[Engine] = None
_new_session: Optional[sessionmaker] = None


def database_url() -> str:
    """
    The configured database URL: DATABASE_URL if set, otherwise a MySQL URL
    built from the legacy DB_HOST/DB_USER/DB_PASSWORD/DB_NAME variables.
    """
    url = os.environ.get('DATABASE_URL')
    if url:
        return url

    host = os.environ.get('DB_HOST', 'localhost')
    user = os.environ.get('DB_USER', 'root')
    password = quote_plus(os.environ.get('DB_PASSWORD', ''))
    name = os.environ.get('DB_NAME', 'portfolio_manager')
    return f"mysql+mysqlconnector://{user}:{password}@{host}/{name}"


def get_engine() -> Engine:
    """
    Get (or lazily create) the process-wide engine. Creation is deferred
    because app.py loads the .env file after importing this module.
    """
    global _engine, _new_session
    if _engine is None:
        _engine = create_engine(database_url(), pool_pre_ping=True, future=True)
        _new_session = sessionmaker(bind=_engine, future=True)
    return _engine


def get_session() -> Session:
    """Get (or lazily open) the SQLAlchemy session for the current request."""
    if 'session' not in g:
        get_engine()
        g.session = _new_session()
    return g.session


def lock_user(session: Session, user_id: int) -> bool:
    """
    Acquire a row lock on the given user, serializing concurrent
    balance-affecting requests (buy/sell/withdraw) for that user so
    balance/holdings checks can't race each other.

    SQLite has no SELECT ... FOR UPDATE (it serializes writers itself), so
    the lock clause is skipped there and this becomes a plain existence check.

    Returns:
        bool: True if the user exists (and is now locked), False otherwise.
    """
    statement = select(User.userId).where(User.userId == user_id)
    if session.get_bind().dialect.name != 'sqlite':
        statement = statement.with_for_update()
    return session.scalar(statement) is not None


def close_session(exception: Optional[BaseException] = None) -> None:
    """Close the request-scoped session, if one was opened."""
    session = g.pop('session', None)
    if session is not None:
        session.close()


def init_db() -> None:
    """
    Create the tables when running on SQLite, so a dev database needs no
    manual setup. MySQL keeps being provisioned from db/schema/schema.sql.
    """
    engine = get_engine()
    if engine.dialect.name == 'sqlite':
        Base.metadata.create_all(engine)


def init_app(app: Flask) -> None:
    """Register the session teardown with the given Flask app."""
    app.teardown_appcontext(close_session)
    init_db()
