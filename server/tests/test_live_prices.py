"""
The upstream price stream: what a streamed message becomes, and which
symbols are considered covered by it.

No socket is opened here. What's worth pinning down is the translation
between Yahoo's wire format and the quote shape the rest of the app
publishes, and the bookkeeping that decides whether the poll loop still
has to cover a symbol - both of which are pure functions of their input.
"""
import pytest

import services.live_prices as live_prices


@pytest.fixture(autouse=True)
def _clear_stream_state():
    """The module's state is process-wide, like the caches."""
    yield
    live_prices._streaming.clear()
    live_prices._last_seen.clear()


@pytest.fixture()
def published(monkeypatch):
    """Quotes the stream handed on, in place of the Socket.IO emit."""
    received = []
    monkeypatch.setattr(live_prices, '_handler', received.append)
    return received


@pytest.fixture()
def sent(monkeypatch):
    """Upstream subscribe/unsubscribe calls, without a socket to make them on."""
    calls = []
    monkeypatch.setattr(live_prices, '_submit', calls.append)
    return calls


def test_a_message_becomes_a_quote():
    quote = live_prices.quote_from({
        'id': 'AAPL',
        'price': 214.5,
        'change': -1.25,
        'change_percent': -0.58,
        'day_high': 216.0,
        'day_low': 213.1,
        'day_volume': '31048200',
    })

    assert quote == {
        'symbol': 'AAPL',
        'currentPrice': 214.5,
        'change': -1.25,
        'changePercent': -0.58,
        'dayHigh': 216.0,
        'dayLow': 213.1,
        'volume': 31048200,
    }


def test_volume_arrives_as_a_number_not_a_string():
    """
    Protobuf's JSON mapping renders 64-bit integers as strings, and volume
    is the only 64-bit field published - so it is the only one that would
    reach the client as "31048200" and render as text.
    """
    quote = live_prices.quote_from({'id': 'AAPL', 'day_volume': '31048200'})

    assert quote['volume'] == 31048200


def test_only_the_fields_that_moved_are_carried():
    """
    A partial message stays partial: the client merges an update over the
    quote it already holds, so absent fields must not become nulls that
    wipe out good values.
    """
    quote = live_prices.quote_from({'id': 'AAPL', 'price': 214.5})

    assert quote == {'symbol': 'AAPL', 'currentPrice': 214.5}


def test_a_message_with_no_symbol_is_dropped():
    assert live_prices.quote_from({'price': 214.5}) is None


def test_a_message_with_nothing_but_a_symbol_is_dropped():
    """Heartbeats and fields we don't publish shouldn't reach a browser."""
    assert live_prices.quote_from({'id': 'AAPL', 'market_hours': 1}) is None


def test_an_unreadable_field_is_skipped_rather_than_failing_the_quote():
    quote = live_prices.quote_from({'id': 'AAPL', 'price': 214.5, 'day_volume': 'lots'})

    assert quote == {'symbol': 'AAPL', 'currentPrice': 214.5}


def test_a_quote_is_published_for_a_watched_symbol(published, sent):
    live_prices.watch(['AAPL'])

    live_prices._on_message({'id': 'AAPL', 'price': 214.5})

    assert published == [{'symbol': 'AAPL', 'currentPrice': 214.5}]


def test_a_quote_for_an_unwatched_symbol_is_dropped(published):
    """A message can still be in flight when the last watcher leaves."""
    live_prices._on_message({'id': 'AAPL', 'price': 214.5})

    assert published == []


def test_a_symbol_that_just_streamed_needs_no_polling(published, sent):
    live_prices.watch(['AAPL'])
    live_prices._on_message({'id': 'AAPL', 'price': 214.5})

    assert live_prices.streamed_recently('AAPL', 5) is True


def test_a_symbol_that_has_gone_quiet_is_polled_again(published, sent):
    live_prices.watch(['AAPL'])
    live_prices._on_message({'id': 'AAPL', 'price': 214.5})
    live_prices._last_seen['AAPL'] -= 30

    assert live_prices.streamed_recently('AAPL', 5) is False


def test_a_symbol_that_has_never_streamed_is_polled():
    assert live_prices.streamed_recently('AAPL', 5) is False


def test_watching_twice_only_subscribes_once(sent):
    """
    api/realtime.py counts watchers; this must not count them a second
    time, or the two tallies would drift apart.
    """
    live_prices.watch(['AAPL', 'MSFT'])
    live_prices.watch(['AAPL'])

    assert len(sent) == 1
    assert live_prices._streaming == {'AAPL', 'MSFT'}


def test_unwatching_stops_the_symbol_streaming(sent):
    live_prices.watch(['AAPL'])
    live_prices.unwatch(['AAPL'])

    assert live_prices._streaming == set()


def test_unwatching_something_unwatched_is_ignored(sent):
    live_prices.unwatch(['AAPL'])

    assert sent == []
