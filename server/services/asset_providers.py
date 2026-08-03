"""
Per-asset-type behavior: how to search, quote, price, and chart each kind of
asset, and whether it can currently be traded.

Everything type-specific lives behind this interface, so the routes and the
buy/sell service never branch on asset type - adding a kind of asset means
adding a class here and registering it below.

Where the data comes from is still someone else's job: the market-traded
providers delegate to services.market_data (the one place yfinance is
called), and bonds delegate to services.bond_pricing.
"""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import services.bond_pricing as bond_pricing
import services.market_data as market_data


class AssetProvider(ABC):
    """Interface implemented by each supported asset type."""

    asset_type: str

    label: str

    supports_limit_orders: bool = False

    streams: bool = False

    @abstractmethod
    def search(self, query: str) -> List[dict]:
        """Search results in the summary shape (symbol, name, quote fields)."""

    @abstractmethod
    def fetch_popular(self) -> List[dict]:
        """The top ~10 popular assets of this type, in the search-result shape."""

    @abstractmethod
    def get_quote(self, ticker: str) -> Optional[dict]:
        """Full detail-page quote for one asset, or None if not found."""

    @abstractmethod
    def get_history(self, ticker: str) -> List[dict]:
        """A year of daily closes: [{'date': str, 'close': float}, ...]."""

    @abstractmethod
    def owns_ticker(self, ticker: str) -> Optional[bool]:
        """
        Whether this ticker really is this kind of asset, or None when that
        can't be established.

        Asked before a ticker is recorded in Assets for the first time,
        because that first answer decides how every later trade of it is
        classified. Distinct from can_trade: a matured bond is still a bond,
        it just can't be bought any more.

        None matters: a ticker nobody recognises and a feed that is down
        look identical from here, and "that isn't a stock" would be a
        misleading thing to say during an outage. Leaving it undecided lets
        the price lookup fail with an accurate error instead.
        """

    @abstractmethod
    def trade_price(self, ticker: str) -> Decimal:
        """
        The price to execute a trade at right now.

        Raises:
            MarketDataUnavailable: if no price could be established, so a
            trade is never booked against a guessed one.
        """

    def valuation_price(self, ticker: str) -> float:
        """
        The price to value an existing holding at. Best-effort by design: a
        portfolio breakdown should still render if one ticker can't be
        priced, so an unavailable price counts as 0.
        """
        try:
            return float(self.trade_price(ticker))
        except Exception:
            return 0.0

    def valuation_prices(self, tickers: List[str]) -> Dict[str, float]:
        """
        Valuation prices for many tickers at once, keyed by ticker.

        The list counterpart of valuation_price, for callers holding a whole
        book - the portfolio breakdown. The default walks valuation_price,
        which is right for a type priced from its own local terms; the
        market-traded types override it with one batched quote call, so
        valuing a dozen holdings costs one upstream lookup rather than a
        dozen. Best-effort in the same way: a ticker that can't be priced
        counts as 0 rather than failing the book.
        """
        return {ticker: self.valuation_price(ticker) for ticker in tickers}

    def can_trade(self, ticker: str) -> Tuple[bool, Optional[str]]:
        """Whether a new purchase of this ticker should be allowed. Defaults to yes."""
        return True, None

    def live_quotes(self, symbols: List[str]) -> Dict[str, dict]:
        """
        Push-able price updates for these symbols, keyed by symbol.

        Empty by default: an asset type streams only if it says it does, so
        a type that is repriced on a schedule rather than quoted - a bond -
        is never subscribed to by accident.
        """
        return {}

    def quote_book(self, tickers: List[str]) -> Dict[str, dict]:
        """
        Name and current price for many tickers at once, keyed by ticker.

        For callers holding a list rather than one asset - a watchlist, a
        holdings table - so the cost is one lookup for the list instead of
        one per row. A ticker that can't be quoted is simply absent.

        The default walks get_quote, which is right for a type priced from
        local terms; the market-traded types override it with a real batch.
        """
        book = {}
        for ticker in tickers:
            try:
                quote = self.get_quote(ticker)
            except Exception:
                continue
            if quote:
                book[ticker] = quote
        return book

    def get_ratings(self, ticker: str) -> Optional[dict]:
        """
        Analyst coverage for this asset, or None when there is none.

        None by default: analysts rate companies, not instruments priced
        from their own terms, so a bond has nothing to report here and
        shouldn't invent it.
        """
        return None


class _MarketTradedProvider(AssetProvider):
    """
    Shared behavior for the asset types quoted by the market data feed.
    They differ only in which search results count as theirs and what
    "popular" means.
    """

    streams = True

    @abstractmethod
    def matches_quote(self, quote: dict) -> bool:
        """Whether a market data search quote belongs to this asset type."""

    def owns_ticker(self, ticker: str) -> Optional[bool]:
        classification = market_data.quote_classification(ticker)
        if classification is None:
            return None
        return self.matches_quote(classification)

    def search(self, query: str) -> List[dict]:
        return market_data.search_assets(query, self.matches_quote)

    def get_quote(self, ticker: str) -> Optional[dict]:
        return market_data.asset_quote(ticker)

    def get_history(self, ticker: str) -> List[dict]:
        return market_data.price_history(ticker)

    def trade_price(self, ticker: str) -> Decimal:
        return market_data.trade_price(ticker)

    def valuation_price(self, ticker: str) -> float:
        return market_data.valuation_price(ticker)

    def valuation_prices(self, tickers: List[str]) -> Dict[str, float]:
        """
        One batched quote call for the whole list, falling back to the
        single-ticker path only for whatever it didn't come back with.
        """
        try:
            quotes = self.live_quotes(tickers)
        except Exception:
            quotes = {}

        prices = {}
        for ticker in tickers:
            price = (quotes.get(ticker) or {}).get('currentPrice')
            prices[ticker] = float(price) if price is not None else self.valuation_price(ticker)
        return prices

    def live_quotes(self, symbols: List[str]) -> Dict[str, dict]:
        return market_data.live_quotes(symbols)

    def quote_book(self, tickers: List[str]) -> Dict[str, dict]:
        quotes = market_data.live_quotes(tickers)
        names = market_data.display_names(list(quotes))
        return {
            ticker: {**quote, 'name': names.get(ticker, ticker)}
            for ticker, quote in quotes.items()
        }

    def get_ratings(self, ticker: str) -> Optional[dict]:
        return market_data.analyst_ratings(ticker)


class StockProvider(_MarketTradedProvider):
    asset_type = 'stock'
    label = 'Stocks'
    supports_limit_orders = True

    US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('exchange') in self.US_EXCHANGES

    def fetch_popular(self) -> List[dict]:
        return market_data.screen_most_active()


class CryptoProvider(_MarketTradedProvider):
    asset_type = 'crypto'
    label = 'Crypto'
    supports_limit_orders = True

    POPULAR_SYMBOLS = {
        'BTC-USD': 'Bitcoin',
        'ETH-USD': 'Ethereum',
        'USDT-USD': 'Tether',
        'XRP-USD': 'XRP',
        'BNB-USD': 'BNB',
        'SOL-USD': 'Solana',
        'USDC-USD': 'USD Coin',
        'DOGE-USD': 'Dogecoin',
        'ADA-USD': 'Cardano',
        'TRX-USD': 'TRON',
    }

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('quoteType') == 'CRYPTOCURRENCY'

    def fetch_popular(self) -> List[dict]:
        return market_data.quote_summaries(self.POPULAR_SYMBOLS)


class BondProvider(AssetProvider):
    """
    Bonds aren't quoted by any feed - they're priced from the catalog in
    services.bond_pricing, as the present value of their remaining cash
    flows. That's also why they have no volume or intraday range.
    """

    asset_type = 'bond'
    label = 'Bonds'

    def search(self, query: str) -> List[dict]:
        today = date.today()
        return [self._summary(bond, today) for bond in bond_pricing.search_bonds(query)]

    def fetch_popular(self) -> List[dict]:
        today = date.today()
        return [
            self._summary(bond, today)
            for bond in bond_pricing.list_bonds()
            if not bond_pricing.is_matured(bond, today)
        ]

    def _summary(self, bond: dict, as_of: date) -> dict:
        return {
            'symbol': bond['ticker'],
            'name': bond['name'],
            'currentPrice': float(bond_pricing.price_bond(bond, as_of)),
        }

    def get_quote(self, ticker: str) -> Optional[dict]:
        bond = bond_pricing.get_bond(ticker)
        if bond is None:
            return None

        history = bond_pricing.price_history(bond)
        closes = [point['close'] for point in history]
        current_price = closes[-1] if closes else float(bond_pricing.price_bond(bond))
        previous_close = closes[-2] if len(closes) > 1 else current_price
        change = current_price - previous_close

        return {
            'symbol': bond['ticker'],
            'name': bond['name'],
            'currentPrice': current_price,
            'change': change,
            'changePercent': (change / previous_close * 100) if previous_close else None,
            'dayLow': None,
            'dayHigh': None,
            'open': None,
            'yearLow': min(closes) if closes else None,
            'yearHigh': max(closes) if closes else None,
            'volume': None,
        }

    def get_history(self, ticker: str) -> List[dict]:
        bond = bond_pricing.get_bond(ticker)
        return bond_pricing.price_history(bond) if bond else []

    def owns_ticker(self, ticker: str) -> Optional[bool]:
        return bond_pricing.get_bond(ticker) is not None

    def trade_price(self, ticker: str) -> Decimal:
        return bond_pricing.trade_price(ticker)

    def can_trade(self, ticker: str) -> Tuple[bool, Optional[str]]:
        bond = bond_pricing.get_bond(ticker)
        if bond is None:
            return False, 'Unknown bond ticker.'
        if bond_pricing.is_matured(bond):
            return False, 'This bond has matured.'
        return True, None


PROVIDERS: Dict[str, AssetProvider] = {
    provider.asset_type: provider
    for provider in (StockProvider(), CryptoProvider(), BondProvider())
}


def capabilities() -> List[dict]:
    """
    What each registered asset type is called and what can be done with it.

    Exists so a client can render its tabs, its labels, and its order-type
    toggles from the registry rather than from its own hardcoded copy of it.
    Registering a provider above is then the only edit a new asset type
    needs on this side, which is what the rest of this module already
    assumed and the client did not.
    """
    return [
        {
            'assetType': provider.asset_type,
            'label': provider.label,
            'streams': provider.streams,
            'supportsLimitOrders': provider.supports_limit_orders,
        }
        for provider in PROVIDERS.values()
    ]
