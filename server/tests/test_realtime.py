"""
The Socket.IO layer: who gets which pushed message.

Exercised through flask_socketio's test client, so the session cookie, the
room membership and the emit all go through the real machinery - which is
the whole point, since the thing under test is that a fill reaches its owner
and nobody else.
"""
import pytest

import realtime
from helpers import register_user


@pytest.fixture(autouse=True)
def stub_quotes(monkeypatch):
    """No upstream calls: what's under test is routing, not prices."""
    monkeypatch.setattr(
        realtime, '_quotes_for',
        lambda watched: {symbol: {'symbol': symbol, 'currentPrice': 100.0} for _, symbol in watched},
    )
    # The broadcaster is a background loop; tests drive the emits directly.
    monkeypatch.setattr(realtime, '_ensure_broadcaster', lambda: None)


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


# A fill happens in the poller's thread long after the request that placed
# the order, so this is the only thing that can tell its owner about it.

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
