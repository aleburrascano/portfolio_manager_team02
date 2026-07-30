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


class _MarketTradedProvider(AssetProvider):
    """
    Shared behavior for the asset types quoted by the market data feed.
    They differ only in which search results count as theirs and what
    "popular" means.
    """

    @abstractmethod
    def matches_quote(self, quote: dict) -> bool:
        """Whether a market data search quote belongs to this asset type."""

    def owns_ticker(self, ticker: str) -> Optional[bool]:
        # The feed reports a ticker's type in the same shape as a search
        # result, so the same predicate answers both questions.
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

    def live_quotes(self, symbols: List[str]) -> Dict[str, dict]:
        return market_data.live_quotes(symbols)


class StockProvider(_MarketTradedProvider):
    asset_type = 'stock'

    # Yahoo Finance exchange codes for Nasdaq, NYSE, and NYSE American/Arca.
    US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('exchange') in self.US_EXCHANGES

    def fetch_popular(self) -> List[dict]:
        return market_data.screen_most_active()


class CryptoProvider(_MarketTradedProvider):
    asset_type = 'crypto'

    # The screener only supports equities/funds/ETFs, so there's no
    # predefined (or constructible) crypto screener to back "popular" the
    # way StockProvider does. Instead, quote a fixed set of the largest
    # cryptocurrencies by market cap directly.
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
        # The catalog is authoritative, so this is never undecided.
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
