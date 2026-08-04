"""
The upstream live price stream.

Yahoo's REST quotes are pull-only, so the pushed feed in api/realtime.py
has always been a five-second poll wearing a socket's clothes: the browser
stopped polling and the server started. Yahoo does publish a streaming feed
and yfinance wraps it, so a price can leave here when it changes rather than
when the loop next comes round.

This module owns that one upstream connection and nothing else. It knows
nothing about Socket.IO - it takes a callback and hands each quote to it -
because what pushes to browsers lives in api/ and services must not import
upward.

Deliberately not the only source of prices. Yahoo's streamer is
undocumented, it goes quiet the moment the market shuts, and it drops
without warning, so the five-second poll stays exactly where it was and
covers whatever hasn't streamed recently. A failure here costs latency,
not prices.

The connection runs on its own asyncio loop in its own thread, and every
upstream send is scheduled onto that loop rather than made from the calling
thread. Subscriptions arrive on Socket.IO handler threads while the loop is
reading messages, so this is the difference between one thread owning the
socket and several racing for it. The async client is also the half of
yfinance that re-subscribes on a timer and reconnects after a drop; the
synchronous one does neither, and a feed that goes quiet after the first
disconnect is the failure this whole module exists to avoid.
"""
import asyncio
import logging
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Set

import yfinance as yf

logger = logging.getLogger(__name__)

Quote = Dict[str, object]

_lock = threading.Lock()
_streaming: Set[str] = set()
_last_seen: Dict[str, float] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None
_socket: Optional[yf.AsyncWebSocket] = None
_handler: Optional[Callable[[Quote], None]] = None
_started = False

# Wire name, our name, and how to read it. The wire names are the protobuf
# field names, which yfinance decodes verbatim; the rest of the app spells
# quote fields the way the REST path does, and the client must not be able
# to tell which of the two a quote arrived by.
#
# The conversions are not decoration. Protobuf's JSON mapping renders 64-bit
# integers as strings - volume arrives as "31048200", not 31048200 - and the
# client types it as a number.
_FIELDS = (
    ('price', 'currentPrice', float),
    ('change', 'change', float),
    ('change_percent', 'changePercent', float),
    ('day_low', 'dayLow', float),
    ('day_high', 'dayHigh', float),
    ('day_volume', 'volume', int),
)


def quote_from(message: dict) -> Optional[Quote]:
    """
    One streamed message in the quote shape, or None if it carries no price
    data we publish.

    Yahoo sends only what moved and protobuf omits anything sitting at its
    default, so a message carrying a new price and nothing else stays that
    small all the way to the browser - which is exactly what the merge at
    the other end was written for.
    """
    symbol = message.get('id')
    if not symbol:
        return None

    quote: Quote = {'symbol': symbol}
    for wire_name, name, read in _FIELDS:
        value = message.get(wire_name)
        if value is None:
            continue
        try:
            quote[name] = read(value)
        except (TypeError, ValueError):
            continue

    return quote if len(quote) > 1 else None


def streamed_recently(symbol: str, within_seconds: float) -> bool:
    """
    Whether this symbol has streamed a quote in the last `within_seconds`.

    The poll loop asks before it fetches, so a symbol the stream already
    covers costs no upstream call, and one that has gone quiet - because
    the market shut, or the feed dropped it, or it simply isn't carried -
    is picked back up without anything having to work out which.
    """
    with _lock:
        seen = _last_seen.get(symbol)
    return seen is not None and (time.monotonic() - seen) < within_seconds


def watch(symbols: Iterable[str]) -> None:
    """
    Stream these symbols, if they aren't already.

    Idempotent, and deliberately not reference-counted: api/realtime.py
    already tracks how many sockets watch each symbol and calls unwatch
    only when the last one goes. Counting here too would be the same tally
    kept twice, and wrong from the first moment the two disagreed.
    """
    with _lock:
        fresh = [symbol for symbol in symbols if symbol not in _streaming]
        _streaming.update(fresh)

    if fresh:
        _submit(lambda socket: socket.subscribe(fresh))


def unwatch(symbols: Iterable[str]) -> None:
    """Stop streaming these symbols. Ones that weren't streaming are ignored."""
    with _lock:
        dropped = [symbol for symbol in symbols if symbol in _streaming]
        _streaming.difference_update(dropped)
        for symbol in dropped:
            _last_seen.pop(symbol, None)

    if dropped:
        _submit(lambda socket: socket.unsubscribe(dropped))


def start(on_quote: Callable[[Quote], None]) -> None:
    """
    Open the stream and hand every quote to `on_quote`.

    Idempotent, and called on the first subscription rather than at import
    for the same reason the poll loop is: a server nobody is watching
    should not be holding a connection open.
    """
    global _handler, _started
    with _lock:
        if _started:
            return
        _started = True
        _handler = on_quote

    threading.Thread(target=_run, name='price-stream', daemon=True).start()


def _run() -> None:
    """
    The stream's own event loop, for the life of the process.

    listen() reconnects on its own and re-subscribes on a timer, so this
    returns only if the client gives up entirely - and by then every symbol
    has stopped streaming, which is already the condition the poll loop
    uses to decide what to cover. Nothing has to be told the stream died.
    """
    global _loop, _socket

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    socket = yf.AsyncWebSocket(verbose=False)
    _loop, _socket = loop, socket

    # Anything subscribed to while this thread was starting: watch() had
    # no loop to schedule onto yet, so its symbols are only in the set.
    with _lock:
        pending: List[str] = list(_streaming)

    async def stream() -> None:
        if pending:
            await socket.subscribe(pending)
        await socket.listen(_on_message)

    try:
        loop.run_until_complete(stream())
    except Exception:
        logger.exception('Price stream stopped; quotes fall back to polling')
    finally:
        _loop, _socket = None, None
        loop.close()


def _on_message(message: dict) -> None:
    """Publish one decoded message, if anyone is still watching its symbol."""
    quote = quote_from(message)
    if quote is None:
        return

    symbol = quote['symbol']
    with _lock:
        if symbol not in _streaming:
            return
        _last_seen[symbol] = time.monotonic()
        handler = _handler

    if handler is not None:
        handler(quote)


def _submit(call) -> None:
    """
    Run one upstream call on the stream's own loop, from any thread.

    Fire and forget: `call` is made on a Socket.IO handler thread, which
    should not be waiting on a network send, and a subscribe that doesn't
    land costs five seconds of polling rather than a price.
    """
    loop, socket = _loop, _socket
    if loop is None or socket is None:
        return

    try:
        asyncio.run_coroutine_threadsafe(call(socket), loop)
    except Exception:
        logger.exception('Could not reach the price stream')
