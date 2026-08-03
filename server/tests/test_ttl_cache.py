"""
The TTL cache, and the market data lookups sitting on it.

Time is moved by monkeypatching the clock rather than by sleeping - the
point under test is the expiry rule, and a suite that waits for it in real
seconds is a suite nobody runs.
"""
import pytest

import services.market_data as market_data
from services.exceptions import MarketDataUnavailable
from services.ttl_cache import MISS, TTLCache


@pytest.fixture()
def clock(monkeypatch):
    """A monotonic clock the test moves by hand."""
    now = [1000.0]
    monkeypatch.setattr('services.ttl_cache.time.monotonic', lambda: now[0])
    return now


def test_a_stored_value_reads_back(clock):
    cache = TTLCache(ttl_seconds=10)
    cache.set('AAPL', {'currentPrice': 100.0})
    assert cache.get('AAPL') == {'currentPrice': 100.0}


def test_an_absent_key_is_a_miss(clock):
    assert TTLCache(ttl_seconds=10).get('AAPL') is MISS


def test_a_value_expires(clock):
    cache = TTLCache(ttl_seconds=10)
    cache.set('AAPL', 100.0)

    clock[0] += 9
    assert cache.get('AAPL') == 100.0
    clock[0] += 2
    assert cache.get('AAPL') is MISS


def test_a_cached_none_is_not_a_miss(clock):
    cache = TTLCache(ttl_seconds=10)
    cache.set('AAPL', None)
    assert cache.get('AAPL') is None


def test_get_or_call_produces_once(clock):
    cache = TTLCache(ttl_seconds=10)
    calls = []

    def produce():
        calls.append(1)
        return 42

    assert cache.get_or_call('k', produce) == 42
    assert cache.get_or_call('k', produce) == 42
    assert len(calls) == 1


def test_get_or_call_produces_again_after_expiry(clock):
    cache = TTLCache(ttl_seconds=10)
    calls = []
    produce = lambda: (calls.append(1), len(calls))[1]

    cache.get_or_call('k', produce)
    clock[0] += 11
    cache.get_or_call('k', produce)
    assert len(calls) == 2


def test_a_raising_producer_is_not_cached(clock):
    cache = TTLCache(ttl_seconds=10)

    def boom():
        raise RuntimeError('upstream down')

    with pytest.raises(RuntimeError):
        cache.get_or_call('k', boom)
    assert cache.get('k') is MISS


def test_sweep_drops_only_expired(clock):
    cache = TTLCache(ttl_seconds=10)
    cache.set('old', 1)
    clock[0] += 6
    cache.set('new', 2)

    clock[0] += 6
    assert cache.sweep() == 1
    assert cache.get('new') == 2


def test_clear_empties_the_cache(clock):
    cache = TTLCache(ttl_seconds=10)
    cache.set('k', 1)
    cache.clear()
    assert len(cache) == 0


def test_price_history_is_fetched_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        market_data, '_price_history',
        lambda ticker, period: calls.append(ticker) or [{'date': '2026-01-01', 'close': 1.0}],
    )

    assert market_data.price_history('AAPL') == [{'date': '2026-01-01', 'close': 1.0}]
    market_data.price_history('AAPL')
    assert calls == ['AAPL']


def test_live_quotes_only_fetches_the_uncached_symbols(monkeypatch):
    fetched = []

    class FakeTicker:
        def __init__(self, symbol):
            fetched.append(symbol)
            self.fast_info = {'lastPrice': 10.0, 'previousClose': 9.0, 'lastVolume': 5}

    class FakeTickers:
        def __init__(self, joined):
            self.tickers = {symbol: FakeTicker(symbol) for symbol in joined.split()}

    monkeypatch.setattr(market_data.yf, 'Tickers', FakeTickers)

    market_data.live_quotes(['AAPL', 'MSFT'])
    assert sorted(fetched) == ['AAPL', 'MSFT']

    fetched.clear()
    market_data.live_quotes(['AAPL', 'MSFT', 'NVDA'])
    assert fetched == ['NVDA']


def test_an_unquotable_symbol_is_remembered_as_absent(monkeypatch):
    fetched = []

    class FakeTickers:
        def __init__(self, joined):
            fetched.extend(joined.split())
            self.tickers = {}

    monkeypatch.setattr(market_data.yf, 'Tickers', FakeTickers)

    assert market_data.live_quotes(['NOPE']) == {}
    market_data.live_quotes(['NOPE'])
    assert fetched == ['NOPE']


def test_trade_price_is_fetched_once(monkeypatch):
    from decimal import Decimal
    calls = []
    monkeypatch.setattr(
        market_data, '_trade_price',
        lambda ticker: calls.append(ticker) or Decimal('123.45'),
    )

    assert market_data.trade_price('AAPL') == Decimal('123.45')
    market_data.trade_price('AAPL')
    assert calls == ['AAPL']


def test_a_failed_trade_price_is_retried(monkeypatch):
    calls = []

    def boom(ticker):
        calls.append(ticker)
        raise MarketDataUnavailable('down')

    monkeypatch.setattr(market_data, '_trade_price', boom)

    for _ in range(2):
        with pytest.raises(MarketDataUnavailable):
            market_data.trade_price('AAPL')
    assert calls == ['AAPL', 'AAPL']


def test_an_undecided_classification_is_not_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(
        market_data, '_quote_classification', lambda ticker: calls.append(ticker) or None,
    )

    market_data.quote_classification('AAPL')
    market_data.quote_classification('AAPL')
    assert calls == ['AAPL', 'AAPL']


def test_a_decided_classification_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(
        market_data, '_quote_classification',
        lambda ticker: calls.append(ticker) or {'quoteType': 'EQUITY', 'exchange': 'NMS'},
    )

    market_data.quote_classification('AAPL')
    market_data.quote_classification('AAPL')
    assert calls == ['AAPL']
