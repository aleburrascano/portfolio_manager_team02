"""
The Socket.IO layer: who gets which pushed message.

Exercised through flask_socketio's test client, so the session cookie, the
room membership and the emit all go through the real machinery - which is
the whole point, since the thing under test is that a fill reaches its owner
and nobody else.
"""
import pytest

import api.realtime as realtime
import services.live_prices as live_prices
from helpers import register_user


@pytest.fixture(autouse=True)
def stub_quotes(monkeypatch):
    """No upstream calls: what's under test is routing, not prices."""
    monkeypatch.setattr(
        realtime, '_quotes_for',
        lambda watched: {symbol: {'symbol': symbol, 'currentPrice': 100.0} for _, symbol in watched},
    )
    monkeypatch.setattr(realtime, '_ensure_broadcaster', lambda: None)


@pytest.fixture(autouse=True)
def stream(monkeypatch):
    """
    The upstream stream, recorded rather than opened.

    Returns {'watched': [...], 'unwatched': [...]} in call order, since
    what matters is that a symbol is dropped upstream exactly when its
    last subscriber goes and not before.
    """
    calls = {'watched': [], 'unwatched': []}
    monkeypatch.setattr(live_prices, 'watch', lambda symbols: calls['watched'].extend(symbols))
    monkeypatch.setattr(live_prices, 'unwatch', lambda symbols: calls['unwatched'].extend(symbols))
    return calls


@pytest.fixture(autouse=True)
def _clear_watchers():
    yield
    realtime._watchers.clear()


def socket_client(app, flask_client):
    return realtime.socketio.test_client(app, flask_test_client=flask_client)


def messages_named(client, name):
    return [m for m in client.get_received() if m['name'] == name]


def test_subscribing_answers_immediately(app, client):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    quotes = messages_named(socket, 'quote')
    assert [m['args'][0]['symbol'] for m in quotes] == ['AAPL']


def test_an_unknown_asset_type_is_ignored(app, client):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'tulips', 'symbols': ['AAPL']})

    assert messages_named(socket, 'quote') == []
    assert realtime._watchers == {}


def test_a_subscription_is_capped(app, client, monkeypatch):
    monkeypatch.setattr(realtime, 'MAX_SYMBOLS_PER_CLIENT', 2)
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['A', 'B', 'C']})

    assert sorted(symbol for _, symbol in realtime._watchers) == ['A', 'B']


def test_unsubscribing_drops_the_watch(app, client):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    socket.emit('unsubscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    assert realtime._watchers == {}


def test_disconnecting_drops_everything_it_watched(app, client):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    socket.disconnect()

    assert realtime._watchers == {}


def test_a_fill_reaches_the_user_who_placed_it(app, client):
    user = register_user(client)
    socket = socket_client(app, client)

    realtime.notify_order_filled({'userId': user['userId'], 'limitOrderId': 1, 'ticker': 'AAPL'})

    [message] = messages_named(socket, 'orderFilled')
    assert message['args'][0]['ticker'] == 'AAPL'


def test_a_fill_does_not_reach_another_user(app, client):
    user = register_user(client)
    socket = socket_client(app, client)

    realtime.notify_order_filled({'userId': user['userId'] + 1, 'limitOrderId': 1, 'ticker': 'AAPL'})

    assert messages_named(socket, 'orderFilled') == []


def test_an_anonymous_socket_still_gets_quotes(app, client):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    assert len(messages_named(socket, 'quote')) == 1


def test_a_fill_with_no_owner_is_dropped_rather_than_broadcast(app, client):
    register_user(client)
    socket = socket_client(app, client)

    realtime.notify_order_filled({'limitOrderId': 1, 'ticker': 'AAPL'})

    assert messages_named(socket, 'orderFilled') == []


def test_subscribing_streams_the_symbol(app, client, stream):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    assert stream['watched'] == ['AAPL']


def test_an_asset_type_that_does_not_stream_is_not_subscribed_upstream(app, client, stream):
    """A bond is repriced from its own terms daily; Yahoo has nothing to send."""
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'bond', 'symbols': ['T-2030']})

    assert stream['watched'] == []


def test_the_last_subscriber_leaving_stops_the_stream(app, client, stream):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    socket.emit('unsubscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    assert stream['unwatched'] == ['AAPL']


def test_a_symbol_someone_else_still_watches_keeps_streaming(app, client, stream):
    """
    The upstream subscription belongs to the symbol, not to the socket:
    one tab closing must not stop the price arriving in another.
    """
    first = socket_client(app, client)
    second = socket_client(app, client)
    first.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    second.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    first.emit('unsubscribe', {'assetType': 'stock', 'symbols': ['AAPL']})

    assert stream['unwatched'] == []


def test_disconnecting_stops_streaming_what_it_alone_watched(app, client, stream):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    socket.disconnect()

    assert stream['unwatched'] == ['AAPL']


def test_a_streamed_quote_reaches_its_room(app, client, stream):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    socket.get_received()

    realtime._push_quote({'symbol': 'AAPL', 'currentPrice': 214.5})

    [message] = messages_named(socket, 'quote')
    assert message['args'][0] == {'symbol': 'AAPL', 'currentPrice': 214.5}


def test_polling_skips_a_symbol_the_stream_is_covering(app, client, stream, monkeypatch):
    monkeypatch.setattr(live_prices, 'streamed_recently', lambda symbol, within: symbol == 'AAPL')
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL', 'MSFT']})

    assert realtime._due_for_polling() == [('stock', 'MSFT')]


def test_polling_covers_everything_when_the_stream_is_silent(app, client, stream, monkeypatch):
    """A shut market, or a stream that has died without saying so."""
    monkeypatch.setattr(live_prices, 'streamed_recently', lambda symbol, within: False)
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL', 'MSFT']})

    assert sorted(realtime._due_for_polling()) == [('stock', 'AAPL'), ('stock', 'MSFT')]


def test_a_streamed_quote_does_not_reach_a_symbol_nobody_asked_for(app, client, stream):
    socket = socket_client(app, client)
    socket.emit('subscribe', {'assetType': 'stock', 'symbols': ['AAPL']})
    socket.get_received()

    realtime._push_quote({'symbol': 'MSFT', 'currentPrice': 410.0})

    assert messages_named(socket, 'quote') == []
