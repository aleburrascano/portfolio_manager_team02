"""
The one place yfinance is called.

Everything above this module deals in plain dicts and Decimals, so
replacing the market data provider - or stubbing it out in tests - is a
change to this file alone. The one exception is close_series, which hands
back the raw pandas Series that bulk historical lookups need.
"""
from decimal import Decimal
from typing import Callable, Dict, List, Optional

import yfinance as yf

from services.exceptions import MarketDataUnavailable

# A yfinance search quote, as passed to a provider's match predicate.
QuoteMatcher = Callable[[dict], bool]


def quote_fields(fast_info) -> dict:
    """Extract price/change/day-range fields from a fast_info object."""
    last_price = fast_info.get('lastPrice')
    previous_close = fast_info.get('previousClose')
    change = last_price - previous_close if last_price is not None and previous_close else None
    return {
        'currentPrice': last_price,
        'change': change,
        'changePercent': change / previous_close * 100 if change is not None and previous_close else None,
        'dayLow': fast_info.get('dayLow'),
        'dayHigh': fast_info.get('dayHigh'),
    }


def quote_summaries(names: Dict[str, str]) -> List[dict]:
    """
    Quote a {symbol: display name} map in one batch.

    A symbol whose quote can't be fetched still comes back, carrying just
    its name - a partial row reads better than a missing one.
    """
    if not names:
        return []

    tickers = yf.Tickers(' '.join(names))
    summaries = []
    for symbol, name in names.items():
        summary = {'symbol': symbol, 'name': name}
        try:
            fast_info = tickers.tickers[symbol].fast_info
            summary['volume'] = fast_info.get('lastVolume')
            summary.update(quote_fields(fast_info))
        except Exception:
            pass
        summaries.append(summary)
    return summaries


def live_quotes(symbols: List[str]) -> Dict[str, dict]:
    """
    Current price fields for many symbols in one batch, keyed by symbol,
    for pushing to subscribed clients.

    Fields with no value are left out rather than sent as null, so a client
    can merge an update over what it already has without a missing field
    wiping out a good one. Symbols that can't be quoted are simply absent.
    """
    if not symbols:
        return {}

    tickers = yf.Tickers(' '.join(symbols))
    quotes = {}
    for symbol in symbols:
        try:
            fast_info = tickers.tickers[symbol].fast_info
            fields = {'volume': fast_info.get('lastVolume'), **quote_fields(fast_info)}
        except Exception:
            continue
        quotes[symbol] = {'symbol': symbol, **{k: v for k, v in fields.items() if v is not None}}
    return quotes


def search_assets(query: str, matches: QuoteMatcher, limit: int = 10) -> List[dict]:
    """
    Search for assets by ticker or name, keeping only the quotes the
    caller's predicate accepts, then quoting the survivors.
    """
    results = yf.Search(query, max_results=limit)
    names = {
        quote['symbol']: quote.get('longname', quote.get('shortname', 'N/A'))
        for quote in results.quotes
        if quote.get('symbol') and matches(quote)
    }
    return quote_summaries(names)


def screen_most_active(limit: int = 10) -> List[dict]:
    """The most actively traded equities, in the search-result shape."""
    results = yf.screen('most_actives')
    return [
        {
            'symbol': quote['symbol'],
            'name': quote.get('shortName', 'N/A'),
            'currentPrice': quote.get('regularMarketPrice'),
            'volume': quote.get('regularMarketVolume'),
            'change': quote.get('regularMarketChange'),
            'changePercent': quote.get('regularMarketChangePercent'),
            'dayLow': quote.get('regularMarketDayLow'),
            'dayHigh': quote.get('regularMarketDayHigh'),
        }
        for quote in results.get('quotes', [])[:limit]
    ]


def asset_quote(ticker: str) -> Optional[dict]:
    """
    Full quote detail for one asset, or None if the ticker isn't known.

    yfinance signals an unknown symbol by raising out of fast_info rather
    than returning empty, so that counts as "not found" too - the caller
    has no way to tell the two apart, and neither do we.
    """
    asset = yf.Ticker(ticker)
    try:
        fast_info = asset.fast_info
        if fast_info.get('lastPrice') is None:
            return None
    except Exception:
        return None

    return {
        'symbol': ticker.upper(),
        'name': asset.info.get('longName', asset.info.get('shortName', ticker.upper())),
        **quote_fields(fast_info),
        'open': fast_info.get('open'),
        'yearLow': fast_info.get('yearLow'),
        'yearHigh': fast_info.get('yearHigh'),
        'volume': fast_info.get('lastVolume'),
    }


def price_history(ticker: str, period: str = '1y') -> List[dict]:
    """Daily closing prices over the given period, oldest first, for charting."""
    prices = yf.Ticker(ticker).history(period=period)
    return [
        {'date': index.strftime('%Y-%m-%d'), 'close': float(row['Close'])}
        for index, row in prices.iterrows()
    ]


def close_series(ticker: str, days: int):
    """
    Daily closing prices as a tz-naive pandas Series indexed by date, for
    callers that need to look prices up at many past dates (the seed
    script). Returns None if the ticker has no history.
    """
    history = yf.Ticker(ticker).history(period=f'{days}d')
    if history.empty:
        return None
    history.index = history.index.tz_localize(None)
    return history['Close']


def trade_price(ticker: str) -> Decimal:
    """
    The price to execute a trade at, as an exact Decimal.

    Raises:
        MarketDataUnavailable: if no price could be fetched, so a trade is
        never booked against a guessed price.
    """
    try:
        close = yf.Ticker(ticker).history(period='1d')['Close'].iloc[0]
    except Exception as e:
        raise MarketDataUnavailable(f'No price available for {ticker}.') from e
    return Decimal(str(close))


def valuation_price(ticker: str) -> float:
    """
    The price to value an existing holding at. Unlike trade_price this is
    best-effort: a portfolio breakdown should still render if one ticker
    can't be quoted, so an unavailable price counts as 0.
    """
    try:
        asset = yf.Ticker(ticker)
        last_price = (getattr(asset, 'fast_info', None) or {}).get('lastPrice')
        if last_price is not None:
            return float(last_price)
        return float(asset.history(period='1d')['Close'].iloc[0])
    except Exception:
        return 0.0
