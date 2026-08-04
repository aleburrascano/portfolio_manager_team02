"""
Live quote push over Socket.IO.

Clients subscribe to the symbols they're currently showing and get a
`quote` event whenever that symbol is re-priced, replacing the polling the
client used to do. Only symbols with at least one subscriber are fetched,
so an idle server does no work at all.

Those re-prices come from two places. Symbols Yahoo streams are pushed the
moment they move (services.live_prices); everything else is picked up by
the five-second poll below, which skips whatever streamed recently. The
poll is not a leftover - it is what covers a shut market, a symbol the
stream doesn't carry, and a stream that has quietly died, none of which
announce themselves.

Quotes are public, matching the REST asset routes - no session required.

The one thing here that isn't public is `orderFilled`. A conditional order
resolves in the poller's own thread, minutes or days after the request that
placed it, so there is no response left to carry the news: without this the
owner's open orders list would sit there showing a pending row that has
already filled. Each session is put in a room named for its logged-in user
on connect, from the same signed cookie the REST routes trust, so a fill
reaches its owner's tabs and nobody else's.
"""
import collections
import logging
import threading
from typing import Dict, List, Set, Tuple

from flask import request, session
from flask_socketio import SocketIO, join_room, leave_room

import services.live_prices as live_prices
from api.authorization import SESSION_USER_KEY
from services.asset_providers import PROVIDERS

BROADCAST_INTERVAL_SECONDS = 5
MAX_SYMBOLS_PER_CLIENT = 50

logger = logging.getLogger(__name__)

socketio = SocketIO()

_watchers: Dict[Tuple[str, str], Set[str]] = {}
_lock = threading.Lock()
_broadcaster_started = False


def _room(symbol: str) -> str:
    return f'quote:{symbol}'


def _user_room(user_id: int) -> str:
    return f'user:{user_id}'


def _watched() -> List[Tuple[str, str]]:
    with _lock:
        return list(_watchers)


def _forget(session_id: str, watched: List[Tuple[str, str]]) -> List[str]:
    """
    Drop a session from the given subscriptions, discarding empty ones.

    Returns the symbols that just lost their last watcher, which are the
    ones worth dropping upstream as well.
    """
    dropped = []
    with _lock:
        for key in watched:
            watchers = _watchers.get(key)
            if watchers is None:
                continue
            watchers.discard(session_id)
            if not watchers:
                del _watchers[key]
                dropped.append(key[1])
    return dropped


def _quotes_for(watched: List[Tuple[str, str]]) -> Dict[str, dict]:
    """
    Ask each asset type's provider for its subscribed symbols, batched per
    type. A provider that doesn't stream returns nothing, so bonds cost no
    lookups however many clients are watching them.
    """
    by_type = collections.defaultdict(list)
    for asset_type, symbol in watched:
        by_type[asset_type].append(symbol)

    quotes = {}
    for asset_type, symbols in by_type.items():
        provider = PROVIDERS.get(asset_type)
        if provider is None:
            continue
        try:
            quotes.update(provider.live_quotes(symbols))
        except Exception:
            continue
    return quotes


def _due_for_polling() -> List[Tuple[str, str]]:
    """
    The watched symbols the stream isn't already covering.

    Filtering before fetching rather than after is the point: a symbol
    arriving live costs no upstream call here at all, so an open market
    makes the poll nearly free instead of doubling the work. When the
    market shuts and the stream falls silent, the same test quietly hands
    every symbol back to polling - which is what keeps the client's
    "updated" timestamp ticking overnight, the one piece of evidence that
    a still price is a live one and not a dead feed.
    """
    return [
        key for key in _watched()
        if not live_prices.streamed_recently(key[1], BROADCAST_INTERVAL_SECONDS)
    ]


def _broadcast_loop() -> None:
    while True:
        socketio.sleep(BROADCAST_INTERVAL_SECONDS)

        watched = _due_for_polling()
        if not watched:
            continue
        for symbol, quote in _quotes_for(watched).items():
            socketio.emit('quote', quote, to=_room(symbol))


def _push_quote(quote: dict) -> None:
    """
    Send one streamed quote to whoever is watching that symbol.

    Called from the stream's thread rather than from a request, so it has
    to name its room - there is no current client to answer.
    """
    socketio.emit('quote', quote, to=_room(quote['symbol']))


def _ensure_broadcaster() -> None:
    """Start the poll loop and the stream on the first subscription, not at import."""
    global _broadcaster_started
    with _lock:
        if _broadcaster_started:
            return
        _broadcaster_started = True
    socketio.start_background_task(_broadcast_loop)
    live_prices.start(_push_quote)


@socketio.on('connect')
def handle_connect(auth=None) -> None:
    """
    Put a logged-in session in its own room, so anything addressed to that
    user reaches every tab they have open and no one else's.

    Identity comes from the signed session cookie, exactly as it does for
    the REST routes - the client never says who it is. An anonymous
    connection simply joins nothing and still gets public quotes.
    """
    user_id = session.get(SESSION_USER_KEY)
    if user_id is not None:
        join_room(_user_room(user_id))


def notify_order_filled(fill: dict) -> None:
    """
    Tell one user that a conditional order of theirs has just filled.

    Called from the poller's thread rather than from a request, and best
    effort by design: the fill is already committed, so a socket that can't
    be reached costs the user a refresh, not a trade.
    """
    _notify_user('orderFilled', fill, fill.get('limitOrderId'))


def notify_bond_redeemed(payout: dict) -> None:
    """
    Tell one user that a bond of theirs has matured and been paid out.

    Same shape of event as a fill and for the same reason: it happens on a
    date rather than in response to anything they did.
    """
    _notify_user('bondRedeemed', payout, payout.get('ticker'))


def _notify_user(event: str, payload: dict, subject) -> None:
    user_id = payload.get('userId')
    if user_id is None:
        return
    try:
        socketio.emit(event, payload, to=_user_room(user_id))
    except Exception:
        logger.exception('Could not announce %s for %s', event, subject)


@socketio.on('subscribe')
def handle_subscribe(payload: dict) -> None:
    """
    Start receiving `quote` events for the given symbols of one asset type.

    Body:
        dict: {'assetType': str, 'symbols': list[str]}
    """
    payload = payload or {}
    asset_type = payload.get('assetType')
    if asset_type not in PROVIDERS:
        return

    symbols = [s for s in payload.get('symbols') or [] if isinstance(s, str) and s]
    symbols = symbols[:MAX_SYMBOLS_PER_CLIENT]
    if not symbols:
        return

    session_id = request.sid
    watched = [(asset_type, symbol) for symbol in symbols]
    with _lock:
        for key in watched:
            _watchers.setdefault(key, set()).add(session_id)
    for symbol in symbols:
        join_room(_room(symbol))

    _ensure_broadcaster()
    if PROVIDERS[asset_type].streams:
        live_prices.watch(symbols)

    for symbol, quote in _quotes_for(watched).items():
        socketio.emit('quote', quote, to=session_id)


@socketio.on('unsubscribe')
def handle_unsubscribe(payload: dict) -> None:
    """Stop receiving `quote` events for the given symbols."""
    payload = payload or {}
    asset_type = payload.get('assetType')
    symbols = [s for s in payload.get('symbols') or [] if isinstance(s, str)]
    for symbol in symbols:
        leave_room(_room(symbol))
    live_prices.unwatch(_forget(request.sid, [(asset_type, symbol) for symbol in symbols]))


@socketio.on('disconnect')
def handle_disconnect(reason: str = None) -> None:
    """Drop everything a departing client was watching."""
    live_prices.unwatch(_forget(request.sid, _watched()))


def init_app(app, cors_allowed_origins) -> None:
    """
    Attach the Socket.IO server to the Flask app.

    `cors_allowed_origins` is whatever Engine.IO accepts - a list of exact
    origins, or a predicate taking one, which is what lets a deployment
    whose frontend hostname changes every release be expressed as a pattern.
    """
    socketio.init_app(app, cors_allowed_origins=cors_allowed_origins, async_mode='threading')
