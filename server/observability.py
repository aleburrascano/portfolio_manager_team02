"""
Knowing what this server is doing.

Two things were invisible before this. What a request cost - a dashboard
load can price a dozen tickers, and there was no way to tell an endpoint
that is slow from one that is merely called often. And whether the process
is healthy in any sense beyond having answered at all: `/` returned
{'status': 'ok'} whether or not the database was reachable, which is
precisely the case a health check exists to catch.

Requests are logged one line each, after the response, with the status and
how long it took. Deliberately not a structured logging library: one line
per request is what a single-service deployment reads through `railway
logs`, and adding a dependency to emit JSON nobody is parsing would be
worse than the gap it closes.
"""
import logging
import time
from typing import Any, Dict

from flask import Flask, g, request
from sqlalchemy import text

logger = logging.getLogger('treetop.request')

# Paths that would otherwise dominate the log without saying anything. The
# health check is matched exactly rather than by prefix, since every path
# starts with a slash; the socket transport is a prefix because its polling
# carries a session id.
QUIET_EXACT = ('/',)
QUIET_PREFIXES = ('/socket.io',)

# Above this a request is worth noticing even though it succeeded. Set where
# it is because a request that prices several tickers upstream lands around
# a second, so this catches the ones doing materially more than that.
SLOW_REQUEST_MS = 2000


def _duration_ms() -> float:
    started = getattr(g, '_request_started', None)
    return (time.monotonic() - started) * 1000 if started else 0.0


def init_app(app: Flask) -> None:
    """Log one line per request, with its status and duration."""

    @app.before_request
    def _start_timer() -> None:
        g._request_started = time.monotonic()

    @app.after_request
    def _log_request(response):
        if request.path in QUIET_EXACT or request.path.startswith(QUIET_PREFIXES):
            return response

        duration = _duration_ms()
        # A slow success is the interesting case and would otherwise be
        # indistinguishable from a fast one at the same level.
        level = logging.WARNING if duration >= SLOW_REQUEST_MS else logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR

        logger.log(
            level, '%s %s %s %.0fms',
            request.method, request.path, response.status_code, duration,
        )
        return response


def health(app: Flask) -> Dict[str, Any]:
    """
    What this process can currently do.

    The database is checked with an actual query rather than assumed from
    the engine existing, because a pool that has lost its connection looks
    identical to a healthy one until something asks it for a row.

    Never raises: a health check that 500s tells a load balancer nothing it
    can act on beyond "down", where "up, but the database is unreachable"
    is the far more useful answer.
    """
    from db.connection import get_engine
    from services.market_data import cache_sizes

    status = {'status': 'ok', 'database': 'ok'}
    try:
        with get_engine().connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception as error:
        app.logger.exception('Health check could not reach the database')
        status['status'] = 'degraded'
        status['database'] = f'unavailable: {type(error).__name__}'

    # How much market data is being served from memory, which is the one
    # number that says whether the cache is doing anything.
    status['marketDataCache'] = cache_sizes()
    return status
