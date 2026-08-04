"""
The one place yfinance is called.

Everything above this module deals in plain dicts and Decimals, so
replacing the market data provider - or stubbing it out in tests - is a
change to this file alone. The one exception is close_series, which hands
back the raw pandas Series that bulk historical lookups need.

Being the only door to the feed is also what makes this the only sensible
place to cache it. Every lookup below goes through a TTL cache sized to how
fast the thing it holds actually moves: a price for seconds, a year of
daily closes for minutes, and what kind of asset a ticker is for a day,
because that never changes at all. Callers are unaware of it - they ask for
what they need as often as they need it, and the fan-out that used to
follow (one dashboard load re-fetching a year of history per held ticker,
the poller re-pricing every pending order's ticker every five seconds)
collapses onto shared entries.
"""
import os
import sys
from decimal import Decimal
from typing import Callable, Dict, List, Optional

import yfinance as yf

from services.exceptions import MarketDataUnavailable
from services.ttl_cache import MISS, TTLCache

QuoteMatcher = Callable[[dict], bool]

QUOTE_FRESHNESS_SECONDS = 5
DAILY_CLOSE_FRESHNESS_SECONDS = 900
ROLLING_24H_FRESHNESS_SECONDS = 300
RATINGS_FRESHNESS_SECONDS = 3600
SEARCH_FRESHNESS_SECONDS = 300
SCREEN_FRESHNESS_SECONDS = 60
NEVER_CHANGES_SECONDS = 86400

_quotes = TTLCache(ttl_seconds=QUOTE_FRESHNESS_SECONDS)
_history = TTLCache(ttl_seconds=DAILY_CLOSE_FRESHNESS_SECONDS)
_rolling = TTLCache(ttl_seconds=ROLLING_24H_FRESHNESS_SECONDS)
_classification = TTLCache(ttl_seconds=NEVER_CHANGES_SECONDS)
_ratings = TTLCache(ttl_seconds=RATINGS_FRESHNESS_SECONDS)
_searches = TTLCache(ttl_seconds=SEARCH_FRESHNESS_SECONDS)
_screens = TTLCache(ttl_seconds=SCREEN_FRESHNESS_SECONDS)
_names = TTLCache(ttl_seconds=NEVER_CHANGES_SECONDS)

_CACHES = (_quotes, _history, _rolling, _classification, _ratings, _searches, _screens, _names)


def clear_caches() -> None:
    """Drop every cached lookup. For tests, and for the seed script."""
    for cache in _CACHES:
        cache.clear()


def sweep_caches() -> int:
    """
    Drop expired entries across every cache. Returns how many went.

    Entries expire on read, so this only matters for keys nobody asks for
    again - a ticker searched once and never revisited. Called on the
    poller's tick, which is the one loop already running on a timer.
    """
    return sum(cache.sweep() for cache in _CACHES)


_BY_NAME = {
    'quotes': _quotes,
    'history': _history,
    'rolling24h': _rolling,
    'classification': _classification,
    'ratings': _ratings,
    'searches': _searches,
    'screens': _screens,
    'names': _names,
}


def cache_sizes() -> Dict[str, dict]:
    """
    Entries held and how often each cache answered, for the health endpoint.

    The hit rate is the number that says whether a window is doing anything:
    a cache that only ever misses is pure overhead, and one that only ever
    hits is probably holding data for longer than it is true.
    """
    return {
        name: {'entries': len(cache), 'hits': cache.hits, 'misses': cache.misses}
        for name, cache in _BY_NAME.items()
    }


def previous_close(asset) -> Optional[float]:
    """
    The previous session's official close, from the chart metadata Yahoo
    returns alongside the price.

    Deliberately not fast_info's own `previousClose`, which yfinance derives
    for itself and which disagrees with the official figure by anything from
    a cent to a couple of dollars - and that figure is the one every other
    app measures the day's change from, so a baseline of our own makes every
    percentage on the page wrong by a different amount. GOOG read $370.00
    against an official $372.47, turning a 1.24% day into 1.91%.

    Free to read: the metadata arrives in the same chart response fast_info
    is built from, so this costs no extra call - but it therefore has to be
    read *after* fast_info has been touched.

    Returns None when the response carried no metadata, leaving the caller
    to fall back rather than invent a baseline.
    """
    metadata = getattr(asset, 'history_metadata', None) or {}
    value = metadata.get('previousClose')
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def quote_fields(fast_info, official_close: Optional[float] = None) -> dict:
    """
    Extract price/change/day-range fields from a fast_info object.

    `official_close` is the baseline the day's change is measured from; see
    previous_close for why it is passed in rather than read from fast_info.
    Falling back to fast_info's own value when it is missing keeps a quote
    that is slightly off in preference to one with no change at all.
    """
    last_price = fast_info.get('lastPrice')
    previous = official_close if official_close is not None else fast_info.get('previousClose')
    change = last_price - previous if last_price is not None and previous else None
    return {
        'currentPrice': last_price,
        'change': change,
        'changePercent': change / previous * 100 if change is not None and previous else None,
        'dayLow': fast_info.get('dayLow'),
        'dayHigh': fast_info.get('dayHigh'),
    }


def _price_book(symbols: List[str]) -> Dict[str, Optional[dict]]:
    """
    The price fields for these symbols, keyed by symbol, from the cache
    where possible and one batched upstream call for whatever is left.

    A symbol that couldn't be quoted maps to None, and that answer is cached
    too - a ticker the feed doesn't know is not worth re-asking about on
    every tick of a five-second loop.

    This is the single path every current price in the app comes through:
    the pushed quote feed, the watchlist, the holdings table, the crypto
    popular list. They share one pool of entries, so a ticker that is both
    held and on screen is fetched once, not twice.
    """
    book: Dict[str, Optional[dict]] = {}
    missing = []
    for symbol in symbols:
        cached = _quotes.get(symbol)
        if cached is MISS:
            missing.append(symbol)
        else:
            book[symbol] = cached

    if missing:
        for symbol, fields in _fetch_prices(missing).items():
            _quotes.set(symbol, fields)
            book[symbol] = fields

    return book


def _fetch_prices(symbols: List[str]) -> Dict[str, Optional[dict]]:
    """One batched upstream call. A symbol that can't be quoted maps to None."""
    tickers = yf.Tickers(' '.join(symbols))
    fetched: Dict[str, Optional[dict]] = {}
    for symbol in symbols:
        try:
            asset = tickers.tickers[symbol]
            fast_info = asset.fast_info
            fetched[symbol] = {
                'volume': fast_info.get('lastVolume'),
                **quote_fields(fast_info, previous_close(asset)),
            }
        except Exception:
            fetched[symbol] = None
    return fetched


HOURS_IN_A_DAY = 24


def rolling_24h_closes(symbols: List[str]) -> Dict[str, float]:
    """
    What each symbol traded at 24 hours ago, keyed by symbol.

    For the markets that never close. A day's change on an exchange-traded
    asset is measured from the previous session's close, but a crypto has no
    session that closed - and every venue quoting one, Yahoo's own quote page
    included, measures the move over a rolling 24 hours instead. Anchored to
    the midnight-UTC bar it reads as roughly double the move by mid-afternoon:
    BTC showed 1.19% against the 0.64% everyone else was showing.

    One batched hourly download for the whole list, cached for minutes,
    because the baseline is a price a day old and leaves the window one bar
    at a time. A symbol without a full day of bars is simply absent, leaving
    its quote measured the ordinary way rather than against a guess.
    """
    closes: Dict[str, float] = {}
    missing = []
    for symbol in symbols:
        cached = _rolling.get(symbol)
        if cached is MISS:
            missing.append(symbol)
        elif cached is not None:
            closes[symbol] = cached

    if missing:
        for symbol, close in _fetch_rolling_24h_closes(missing).items():
            _rolling.set(symbol, close)
            if close is not None:
                closes[symbol] = close
    return closes


def _fetch_rolling_24h_closes(symbols: List[str]) -> Dict[str, Optional[float]]:
    """
    One batched hourly download. A symbol the feed didn't carry a full day
    of maps to None, and that answer is cached too - an hourly series that
    isn't there won't be there on the next tick either.
    """
    try:
        frame = yf.download(
            symbols, period='2d', interval='1h', auto_adjust=False,
            progress=False, group_by='ticker', threads=False,
        )
    except Exception:
        return {symbol: None for symbol in symbols}

    fetched: Dict[str, Optional[float]] = {}
    for symbol in symbols:
        try:
            series = frame[symbol]['Close'].dropna()
            fetched[symbol] = (
                float(series.iloc[-(HOURS_IN_A_DAY + 1)]) if len(series) > HOURS_IN_A_DAY else None
            )
        except Exception:
            fetched[symbol] = None
    return fetched


def with_24h_change(rows: List[dict]) -> List[dict]:
    """
    The same quotes with `change` and `changePercent` measured over the last
    24 hours rather than from the previous close.

    Returns new rows rather than editing the given ones, which may be the
    cached originals. A row with no 24-hour baseline, or no price to compare,
    is passed through untouched.
    """
    if not rows:
        return rows

    baselines = rolling_24h_closes([row['symbol'] for row in rows if row.get('symbol')])

    restated = []
    for row in rows:
        baseline = baselines.get(row.get('symbol'))
        price = row.get('currentPrice')
        if not baseline or price is None:
            restated.append(row)
            continue
        change = price - baseline
        restated.append({**row, 'change': change, 'changePercent': change / baseline * 100})
    return restated


def display_names(symbols: List[str]) -> Dict[str, str]:
    """
    The long name for each symbol, keyed by symbol, falling back to the
    symbol itself when the feed doesn't offer one.

    Names come from `.info`, which is the expensive half of a quote, so they
    are held for a day - a company's name is as stable as its exchange. That
    is what lets a caller who needs names *and* prices batch the prices
    through _price_book and pay for the names only once.
    """
    known = {}
    for symbol in symbols:
        cached = _names.get(symbol)
        if cached is not MISS:
            known[symbol] = cached
            continue
        try:
            name = _fetch_display_name(symbol)
        except Exception:
            known[symbol] = symbol
            continue
        _names.set(symbol, name)
        known[symbol] = name
    return known


def _fetch_display_name(symbol: str) -> str:
    info = yf.Ticker(symbol).info or {}
    return info.get('longName') or info.get('shortName') or symbol


def quote_summaries(names: Dict[str, str]) -> List[dict]:
    """
    Quote a {symbol: display name} map in one batch.

    A symbol whose quote can't be fetched still comes back, carrying just
    its name - a partial row reads better than a missing one.
    """
    if not names:
        return []

    book = _price_book(list(names))
    return [
        {'symbol': symbol, 'name': name, **(book.get(symbol) or {})}
        for symbol, name in names.items()
    ]


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

    return {
        symbol: {'symbol': symbol, **{k: v for k, v in fields.items() if v is not None}}
        for symbol, fields in _price_book(symbols).items()
        if fields is not None
    }


def search_assets(query: str, matches: QuoteMatcher, limit: int = 10) -> List[dict]:
    """
    Search for assets by ticker or name, keeping only the quotes the
    caller's predicate accepts, then quoting the survivors.
    """
    matcher = getattr(matches, '__qualname__', repr(matches))
    names = _searches.get_or_call(
        (query, limit, matcher), lambda: _search_names(query, matches, limit)
    )
    return quote_summaries(names)


def _search_names(query: str, matches: QuoteMatcher, limit: int) -> Dict[str, str]:
    """The {symbol: name} the feed matches for this query, filtered by type."""
    results = yf.Search(query, max_results=limit)
    return {
        quote['symbol']: quote.get('longname', quote.get('shortname', 'N/A'))
        for quote in results.quotes
        if quote.get('symbol') and matches(quote)
    }


def screen_most_active(limit: int = 10) -> List[dict]:
    """The most actively traded equities, in the search-result shape."""
    return _screens.get_or_call(('most_actives', limit), lambda: _screen_most_active(limit))


def _screen_most_active(limit: int) -> List[dict]:
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


def quote_classification(ticker: str) -> Optional[dict]:
    """
    The fields that say what kind of asset a ticker is, in the same shape a
    search result has - so a provider's match predicate works on either one.

    Returns None when the feed says nothing about what the ticker is -
    whether because the symbol is unknown or because the lookup failed. The
    caller can't tell those apart and shouldn't pretend to.
    """
    cached = _classification.get(ticker)
    if cached is not MISS:
        return cached

    classification = _quote_classification(ticker)
    if classification is not None:
        _classification.set(ticker, classification)
    return classification


def _quote_classification(ticker: str) -> Optional[dict]:
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return None

    classification = {'quoteType': info.get('quoteType'), 'exchange': info.get('exchange')}
    if not any(classification.values()):
        return None
    return classification


def asset_quote(ticker: str) -> Optional[dict]:
    """
    Full quote detail for one asset, or None if the ticker isn't known.

    yfinance signals an unknown symbol by raising out of fast_info rather
    than returning empty, so that counts as "not found" too - the caller
    has no way to tell the two apart, and neither do we.
    """
    return _quotes.get_or_call(('detail', ticker), lambda: _asset_quote(ticker))


def _asset_quote(ticker: str) -> Optional[dict]:
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
        **quote_fields(fast_info, previous_close(asset)),
        'open': fast_info.get('open'),
        'yearLow': fast_info.get('yearLow'),
        'yearHigh': fast_info.get('yearHigh'),
        'volume': fast_info.get('lastVolume'),
    }


RECOMMENDATION_BUCKETS = [
    ('strongBuy', 'Strong buy'),
    ('buy', 'Buy'),
    ('hold', 'Hold'),
    ('sell', 'Sell'),
    ('strongSell', 'Strong sell'),
]


def _consensus_distribution(asset) -> List[dict]:
    """
    How many analysts land in each bucket, most recent period only.

    Returns an empty list when the feed has no recommendations, which is
    normal for smaller listings and for anything that isn't an equity.
    """
    try:
        table = asset.recommendations
    except Exception:
        return []
    if table is None or getattr(table, 'empty', True):
        return []

    latest = table.iloc[0]
    distribution = []
    for column, label in RECOMMENDATION_BUCKETS:
        if column not in latest:
            continue
        try:
            count = int(latest[column])
        except (TypeError, ValueError):
            continue
        distribution.append({'label': label, 'count': count})
    return distribution if any(row['count'] for row in distribution) else []


def analyst_ratings(ticker: str) -> Optional[dict]:
    """
    Wall Street's view of a ticker: the consensus call, the price targets,
    and how the analysts split.

    Returns None when the feed has nothing to say - plenty of tickers have
    no coverage at all, and an empty panel is better than a fabricated one.
    """
    return _ratings.get_or_call(ticker, lambda: _analyst_ratings(ticker))


def _analyst_ratings(ticker: str) -> Optional[dict]:
    try:
        asset = yf.Ticker(ticker)
        info = asset.info or {}
    except Exception:
        return None

    distribution = _consensus_distribution(asset)
    analyst_count = info.get('numberOfAnalystOpinions')
    target = info.get('targetMeanPrice')

    if not distribution and not analyst_count and target is None:
        return None

    return {
        'consensus': info.get('recommendationKey'),
        'score': info.get('recommendationMean'),
        'analystCount': analyst_count,
        'targetLow': info.get('targetLowPrice'),
        'targetMean': target,
        'targetHigh': info.get('targetHighPrice'),
        'currentPrice': info.get('currentPrice') or info.get('regularMarketPrice'),
        'distribution': distribution,
    }


def period_covering(days: int) -> str:
    """
    The smallest yfinance period string that spans `days` of history.

    The performance chart offers windows up to five years but used to fetch
    a fixed year of closes, so anything held longer than that was valued at
    zero for every day before the window began. Mapping the requested span
    to a period that actually covers it is what keeps an older holding on
    the chart instead of collapsing it to cash.
    """
    for threshold, period in ((365, '1y'), (730, '2y'), (1825, '5y')):
        if days <= threshold:
            return period
    return 'max'


def price_history(ticker: str, period: str = '1y') -> List[dict]:
    """
    Daily closing prices over the given period, oldest first, for charting.

    The most expensive call in this module and the one asked for most
    redundantly: the performance chart fetches a year per ticker the user
    has ever traded, and re-fetches all of it whenever their balance moves.
    """
    return _history.get_or_call((ticker, period), lambda: _price_history(ticker, period))


def _price_history(ticker: str, period: str) -> List[dict]:
    """
    Closes as they were actually traded, not back-adjusted for dividends.

    yfinance adjusts by default, which quietly puts this series on a
    different scale from every other price in the app: KO's close a year ago
    came back 2.75% under what it traded at, so the chart's own peak sat
    below the 52-week high printed beside it, and the performance replay
    valued a holding at prices it could never have been bought or sold at.
    Splits are applied either way, so nothing is lost by turning this off.
    """
    prices = yf.Ticker(ticker).history(period=period, auto_adjust=False)
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
    history = yf.Ticker(ticker).history(period=f'{days}d', auto_adjust=False)
    if history.empty:
        return None
    history.index = history.index.tz_localize(None)
    return history['Close']


def trade_price(ticker: str) -> Decimal:
    """
    The price to execute a trade at, as an exact Decimal.

    Cached for the same few seconds as every other price, which also means
    the number a trade books at is the one the user was just shown rather
    than a second, marginally different fetch.

    Raises:
        MarketDataUnavailable: if no price could be fetched, so a trade is
        never booked against a guessed price. A failure is not cached, so an
        outage is retried rather than remembered.
    """
    return _quotes.get_or_call(('trade', ticker), lambda: _trade_price(ticker))


def _trade_price(ticker: str) -> Decimal:
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

    Reads the same cached price book the quote feed fills, so valuing a
    ticker that is already on someone's screen costs nothing.
    """
    fields = _price_book([ticker]).get(ticker)
    if fields and fields.get('currentPrice') is not None:
        return float(fields['currentPrice'])

    try:
        return float(trade_price(ticker))
    except Exception:
        return 0.0


if os.environ.get('MARKET_DATA', '').lower() == 'fake':
    from services import fake_feed

    fake_feed.install(sys.modules[__name__])
