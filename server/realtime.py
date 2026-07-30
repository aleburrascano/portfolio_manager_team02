"""
Live quote push over Socket.IO.

Clients subscribe to the symbols they're currently showing and get a
`quote` event whenever that symbol is re-priced, replacing the polling the
client used to do. Only symbols with at least one subscriber are fetched,
so an idle server does no work at all.

Quotes are public, matching the REST asset routes - no session required.
"""
import collections
import threading
from typing import Dict, List, Set, Tuple

from flask import request
from flask_socketio import SocketIO, join_room, leave_room

from services.asset_providers import PROVIDERS

BROADCAST_INTERVAL_SECONDS = 5
MAX_SYMBOLS_PER_CLIENT = 50

socketio = SocketIO()

# (asset type, symbol) -> the session ids watching it. The type is carried
# so the broadcaster can ask the right provider for a price; a symbol alone
# wouldn't say who owns it. Guarded by _lock because socket handlers and the
# broadcaster thread both touch it.
_watchers: Dict[Tuple[str, str], Set[str]] = {}
_lock = threading.Lock()
_broadcaster_started = False


def _room(symbol: str) -> str:
    return f'quote:{symbol}'


def _watched() -> List[Tuple[str, str]]:
    with _lock:
        return list(_watchers)


def _forget(session_id: str, watched: List[Tuple[str, str]]) -> None:
    """Drop a session from the given subscriptions, discarding empty ones."""
    with _lock:
        for key in watched:
            watchers = _watchers.get(key)
            if watchers is None:
                continue
            watchers.discard(session_id)
            if not watchers:
                del _watchers[key]


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
            # One type failing shouldn't stop the others.
            continue
    return quotes


def _broadcast_loop() -> None:
    while True:
        # Sleeps first: subscribing already sends the current quote back, so
        # fetching again straight away would just repeat it.
        socketio.sleep(BROADCAST_INTERVAL_SECONDS)

        watched = _watched()
        if not watched:
            continue
        for symbol, quote in _quotes_for(watched).items():
            socketio.emit('quote', quote, to=_room(symbol))


def _ensure_broadcaster() -> None:
    """Start the broadcaster on the first subscription, not at import."""
    global _broadcaster_started
    with _lock:
        if _broadcaster_started:
            return
        _broadcaster_started = True
    socketio.start_background_task(_broadcast_loop)


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

    # Answer immediately so a subscriber doesn't wait a whole interval.
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
    _forget(request.sid, [(asset_type, symbol) for symbol in symbols])


@socketio.on('disconnect')
def handle_disconnect(reason: str = None) -> None:
    """Drop everything a departing client was watching."""
    _forget(request.sid, _watched())


def init_app(app, cors_origins) -> None:
    """Attach the Socket.IO server to the Flask app."""
    socketio.init_app(app, cors_allowed_origins=cors_origins, async_mode='threading')
