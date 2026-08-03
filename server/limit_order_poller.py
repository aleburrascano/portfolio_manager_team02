"""
Background evaluation of pending limit orders, independent of who (if
anyone) is watching the app - unlike realtime.py's broadcast loop, which
only fetches prices while a client is subscribed, a limit order has to keep
being checked whether or not its owner has the app open.

Each tick opens its own throwaway Flask app context, so services.limit_orders
can call db.connection.get_session() exactly as a request would; the
context's teardown (already registered by db.connection.init_app) closes
that tick's session on the way out, so there is no session lifecycle code
here at all.
"""
import logging
import threading

from realtime import notify_order_filled
from services.limit_orders import evaluate_pending_orders
from services.market_data import sweep_caches

POLL_INTERVAL_SECONDS = 5

logger = logging.getLogger(__name__)


def run_once(app) -> int:
    """
    One tick: evaluate all pending orders under a fresh app context, and
    tell each owner about anything that filled.

    The announcing happens here rather than in services.limit_orders because
    a service never imports Flask, and the socket is Flask's. This module
    already sits on that side of the line.

    Returns:
        int: how many orders filled this tick.
    """
    with app.app_context():
        try:
            # Piggybacked here rather than given its own thread: market data
            # entries expire on read, so this only clears out tickers nobody
            # asked about again, and this is the one loop already on a timer.
            sweep_caches()
            fills = evaluate_pending_orders()
        except Exception:
            # One bad tick (a DB hiccup, an upstream outage) must not kill
            # the thread - there is no supervisor to restart it.
            logger.exception('Limit order evaluation failed')
            return 0

        for fill in fills:
            notify_order_filled(fill)
        return len(fills)


def _run(app, stop_event: threading.Event) -> None:
    while True:
        # Sleeps first: this thread starts as a side effect of importing
        # app.py, before anything has confirmed the schema this process's
        # own engine will bind to is actually migrated - a deploy step that
        # normally finishes well before the app is reachable, but which
        # tooling (this repo's e2e harness rebuilds its SQLite file on every
        # run) can still be mid-flight at process start. The wait is a cheap
        # way to not be the first thing to touch the database.
        if stop_event.wait(POLL_INTERVAL_SECONDS):
            return
        run_once(app)


def start(app) -> threading.Event:
    """
    Start the poller thread for this app.

    Returns the Event that stops it. app.py never needs it - the thread is
    daemonized and dies with the process - but tests that spin up their own
    app instance can use it to shut the thread down cleanly.
    """
    stop_event = threading.Event()
    threading.Thread(target=_run, args=(app, stop_event), daemon=True).start()
    return stop_event
