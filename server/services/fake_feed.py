"""
A deterministic stand-in for the market data feed, for end-to-end tests.

The e2e suite could only ever trade bonds, because bonds are priced from
the local catalog and everything else came from live Yahoo. That left the
whole stock and crypto path - and every conditional order, whose entire
point is filling when a price crosses - untestable through the browser. The
limit order spec says so in its own header, and the one place it did touch
live data (searching "Apple" and asserting the heading "Apple Inc.") made CI
depend on a third party being up and on not renaming a company.

Installed over services.market_data's fetch primitives when MARKET_DATA is
set to `fake`, so it replaces exactly the calls that would have left the
process and nothing above them. The caching, batching, classification and
error handling under test are the real ones.

Prices are a pure function of (symbol, date): stable within a run, stable
across runs, and different enough per symbol that a test asserting on one
is asserting on something. Nothing here is random - a flaky price would
reproduce the problem this exists to remove.
"""
import hashlib
import math
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

# The catalog a test can rely on. Small on purpose: these are the tickers
# the specs name, and a symbol outside it is treated as unknown - which is
# itself a path worth being able to exercise.
CATALOG = {
    'AAPL': {'name': 'Apple Inc.', 'quoteType': 'EQUITY', 'exchange': 'NMS'},
    'MSFT': {'name': 'Microsoft Corporation', 'quoteType': 'EQUITY', 'exchange': 'NMS'},
    'NVDA': {'name': 'NVIDIA Corporation', 'quoteType': 'EQUITY', 'exchange': 'NMS'},
    'TSLA': {'name': 'Tesla, Inc.', 'quoteType': 'EQUITY', 'exchange': 'NMS'},
    'BTC-USD': {'name': 'Bitcoin USD', 'quoteType': 'CRYPTOCURRENCY', 'exchange': 'CCC'},
    'ETH-USD': {'name': 'Ethereum USD', 'quoteType': 'CRYPTOCURRENCY', 'exchange': 'CCC'},
}


def enabled() -> bool:
    return os.environ.get('MARKET_DATA', '').lower() == 'fake'


def _base_price(symbol: str) -> float:
    """
    A stable price per symbol, from a hash of its name.

    Hashed rather than listed so a symbol nobody thought to add still has a
    sensible price, and md5 rather than hash() because Python salts the
    latter per process - which would make prices differ between the web
    process and the poller.
    """
    digest = hashlib.md5(symbol.encode()).hexdigest()
    return 20 + int(digest[:6], 16) % 480 + int(digest[6:8], 16) / 256


def _close_on(symbol: str, day: date) -> float:
    """
    That symbol's close on that date.

    A slow sine over the day-of-year, so a year of history draws as a curve
    rather than a flat line, with the amplitude tied to the symbol so two
    tickers don't move in lockstep.
    """
    base = _base_price(symbol)
    swing = 0.12 + (int(hashlib.md5(symbol.encode()).hexdigest()[8:10], 16) % 16) / 100
    return round(base * (1 + swing * math.sin(day.toordinal() / 30)), 2)


def _quote(symbol: str) -> Optional[dict]:
    if symbol not in CATALOG:
        return None

    today = date.today()
    price = _close_on(symbol, today)
    previous = _close_on(symbol, today - timedelta(days=1))
    change = round(price - previous, 2)

    return {
        'currentPrice': price,
        'change': change,
        'changePercent': round(change / previous * 100, 4) if previous else None,
        'dayLow': round(min(price, previous) * 0.99, 2),
        'dayHigh': round(max(price, previous) * 1.01, 2),
        'volume': 1_000_000 + int(hashlib.md5(symbol.encode()).hexdigest()[:4], 16),
    }


def fetch_prices(symbols: List[str]) -> Dict[str, Optional[dict]]:
    return {symbol: _quote(symbol) for symbol in symbols}


def fetch_display_name(symbol: str) -> str:
    entry = CATALOG.get(symbol)
    return entry['name'] if entry else symbol


def quote_classification(ticker: str) -> Optional[dict]:
    entry = CATALOG.get(ticker)
    if entry is None:
        return None
    return {'quoteType': entry['quoteType'], 'exchange': entry['exchange']}


def search_names(query: str, matches, limit: int) -> Dict[str, str]:
    """Match on symbol or name, then let the caller's predicate filter by type."""
    needle = query.strip().lower()
    found = {}
    for symbol, entry in CATALOG.items():
        if needle not in symbol.lower() and needle not in entry['name'].lower():
            continue
        if not matches({'symbol': symbol, **entry}):
            continue
        found[symbol] = entry['name']
        if len(found) >= limit:
            break
    return found


def screen_most_active(limit: int) -> List[dict]:
    return [
        {'symbol': symbol, 'name': entry['name'], **(_quote(symbol) or {})}
        for symbol, entry in CATALOG.items()
        if entry['quoteType'] == 'EQUITY'
    ][:limit]


def price_history(ticker: str, period: str) -> List[dict]:
    if ticker not in CATALOG:
        return []

    days = {'1y': 365, '5y': 1825}.get(period, 365)
    today = date.today()
    return [
        {
            'date': (today - timedelta(days=offset)).strftime('%Y-%m-%d'),
            'close': _close_on(ticker, today - timedelta(days=offset)),
        }
        for offset in range(days, -1, -1)
    ]


def trade_price(ticker: str) -> Decimal:
    from services.exceptions import MarketDataUnavailable

    if ticker not in CATALOG:
        raise MarketDataUnavailable(f'No price available for {ticker}.')
    return Decimal(str(_close_on(ticker, date.today())))


def analyst_ratings(ticker: str) -> Optional[dict]:
    if CATALOG.get(ticker, {}).get('quoteType') != 'EQUITY':
        return None

    price = _close_on(ticker, date.today())
    return {
        'consensus': 'buy',
        'score': 2.0,
        'analystCount': 30,
        'targetLow': round(price * 0.8, 2),
        'targetMean': round(price * 1.1, 2),
        'targetHigh': round(price * 1.4, 2),
        'currentPrice': price,
        'distribution': [
            {'label': 'Strong buy', 'count': 12},
            {'label': 'Buy', 'count': 10},
            {'label': 'Hold', 'count': 8},
        ],
    }


def install(market_data) -> None:
    """Point market_data's fetch primitives at this module."""
    market_data._fetch_prices = fetch_prices
    market_data._fetch_display_name = fetch_display_name
    market_data._quote_classification = quote_classification
    market_data._search_names = search_names
    market_data._screen_most_active = screen_most_active
    market_data._price_history = price_history
    market_data._trade_price = trade_price
    market_data._analyst_ratings = analyst_ratings
