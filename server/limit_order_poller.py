"""
Background work that has to happen whether or not anyone is watching the
app - unlike realtime.py's broadcast loop, which only fetches prices while a
client is subscribed.

Two things qualify. A limit order has to keep being checked against the
market whether or not its owner has the app open, and a bond matures on a
date rather than when someone next signs in.

Each tick opens its own throwaway Flask app context, so the services can
call db.connection.get_session() exactly as a request would; the context's
teardown (already registered by db.connection.init_app) closes that tick's
session on the way out, so there is no session lifecycle code here at all.
"""
import logging
import os
import threading

from realtime import notify_bond_redeemed, notify_order_filled
from services.bond_redemption import redeem_matured_bonds
from services.limit_orders import evaluate_pending_orders
from services.market_data import sweep_caches

POLL_INTERVAL_SECONDS = float(os.environ.get('POLL_INTERVAL_SECONDS', '5'))

STARTUP_DELAY_SECONDS = 5

logger = logging.getLogger(__name__)


def run_once(app) -> int:
    """
    One tick: fill what can be filled, redeem what has matured, and tell
    each owner about anything that happened to them.

    The announcing happens here rather than in the services because a
    service never imports Flask, and the socket is Flask's. This module
    already sits on that side of the line.

    Returns:
        int: how many orders filled this tick.
    """
    with app.app_context():
        try:
            sweep_caches()
            fills = evaluate_pending_orders()
        except Exception:
            logger.exception('Limit order evaluation failed')
            fills = []

        try:
            payouts = redeem_matured_bonds()
        except Exception:
            logger.exception('Bond redemption failed')
            payouts = []

        for fill in fills:
            notify_order_filled(fill)
        for payout in payouts:
            notify_bond_redeemed(payout)
        return len(fills)


def _run(app, stop_event: threading.Event) -> None:
    if stop_event.wait(STARTUP_DELAY_SECONDS):
        return

    while True:
        run_once(app)
        if stop_event.wait(POLL_INTERVAL_SECONDS):
            return


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
