"""
Live quote push over Socket.IO.

Clients subscribe to the symbols they're currently showing and get a
`quote` event whenever that symbol is re-priced, replacing the polling the
client used to do. Only symbols with at least one subscriber are fetched,
so an idle server does no work at all.

Quotes are public, matching the REST asset routes - no session required.
"""
import threading
from typing import Dict, List, Set

from flask import request
from flask_socketio import SocketIO, join_room, leave_room

import services.market_data as market_data

BROADCAST_INTERVAL_SECONDS = 5
MAX_SYMBOLS_PER_CLIENT = 50

socketio = SocketIO()

# symbol -> the session ids watching it. Guarded by _lock because socket
# handlers and the broadcaster thread both touch it.
_watchers: Dict[str, Set[str]] = {}
_lock = threading.Lock()
_broadcaster_started = False


def _room(symbol: str) -> str:
    return f'quote:{symbol}'


def _watched_symbols() -> List[str]:
    with _lock:
        return list(_watchers)


def _forget(session_id: str, symbols: List[str]) -> None:
    """Drop a session from the given symbols, discarding symbols left empty."""
    with _lock:
        for symbol in symbols:
            watchers = _watchers.get(symbol)
            if watchers is None:
                continue
            watchers.discard(session_id)
            if not watchers:
                del _watchers[symbol]


def _broadcast_loop() -> None:
    while True:
        # Sleeps first: subscribing already sends the current quote back, so
        # fetching again straight away would just repeat it.
        socketio.sleep(BROADCAST_INTERVAL_SECONDS)

        symbols = _watched_symbols()
        if not symbols:
            continue
        try:
            for symbol, quote in market_data.live_quotes(symbols).items():
                socketio.emit('quote', quote, to=_room(symbol))
        except Exception:
            # A bad fetch shouldn't kill the loop - try again next tick.
            pass


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
    """Start receiving `quote` events for the given symbols."""
    symbols = (payload or {}).get('symbols') or []
    symbols = [s for s in symbols if isinstance(s, str) and s][:MAX_SYMBOLS_PER_CLIENT]
    if not symbols:
        return

    session_id = request.sid
    with _lock:
        for symbol in symbols:
            _watchers.setdefault(symbol, set()).add(session_id)
    for symbol in symbols:
        join_room(_room(symbol))

    _ensure_broadcaster()

    # Answer immediately so a subscriber doesn't wait a whole interval.
    for symbol, quote in market_data.live_quotes(symbols).items():
        socketio.emit('quote', quote, to=session_id)


@socketio.on('unsubscribe')
def handle_unsubscribe(payload: dict) -> None:
    """Stop receiving `quote` events for the given symbols."""
    symbols = [s for s in (payload or {}).get('symbols') or [] if isinstance(s, str)]
    for symbol in symbols:
        leave_room(_room(symbol))
    _forget(request.sid, symbols)


@socketio.on('disconnect')
def handle_disconnect(reason: str = None) -> None:
    """Drop everything a departing client was watching."""
    _forget(request.sid, _watched_symbols())


def init_app(app, cors_origins) -> None:
    """Attach the Socket.IO server to the Flask app."""
    socketio.init_app(app, cors_allowed_origins=cors_origins, async_mode='threading')
