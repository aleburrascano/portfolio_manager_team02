"""
Per-asset-type behavior shared by the assets routes and the buy/sell
service: how to search, quote, price, and chart each supported asset type.
"""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

import yfinance as yf

import services.bond_pricing as bond_pricing


def _quote_fields(fast_info: dict) -> dict:
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


def _yfinance_search(query: str, matches_quote) -> list[dict]:
    search = yf.Search(query, max_results=10)
    names = {}
    for quote in search.quotes:
        symbol = quote.get('symbol')
        if symbol and matches_quote(quote):
            names[symbol] = quote.get('longname', quote.get('shortname', 'N/A'))

    results = []
    if names:
        tickers = yf.Tickers(' '.join(names.keys()))
        for symbol, name in names.items():
            asset = {'symbol': symbol, 'name': name}
            try:
                asset.update(_quote_fields(tickers.tickers[symbol].fast_info))
            except Exception:
                pass
            results.append(asset)
    return results


def _yfinance_quote(ticker: str) -> Optional[dict]:
    asset = yf.Ticker(ticker)
    fast_info = asset.fast_info
    last_price = fast_info.get('lastPrice')
    if last_price is None:
        return None

    return {
        'symbol': ticker.upper(),
        'name': asset.info.get('longName', asset.info.get('shortName', ticker.upper())),
        **_quote_fields(fast_info),
        'open': fast_info.get('open'),
        'yearLow': fast_info.get('yearLow'),
        'yearHigh': fast_info.get('yearHigh'),
        'volume': fast_info.get('lastVolume'),
    }


def _yfinance_history(ticker: str) -> list[dict]:
    prices = yf.Ticker(ticker).history(period='1y')
    return [
        {'date': index.strftime('%Y-%m-%d'), 'close': float(row['Close'])}
        for index, row in prices.iterrows()
    ]


def _yfinance_current_price(ticker: str) -> Decimal:
    return Decimal(str(yf.Ticker(ticker).history(period='1d')['Close'].iloc[0]))


class AssetProvider(ABC):
    """Interface implemented by each supported asset type."""

    asset_type: str

    @abstractmethod
    def search(self, query: str) -> list[dict]:
        """Search results in the summary shape (symbol, name, quote fields)."""

    @abstractmethod
    def fetch_popular(self) -> list[dict]:
        """The top ~10 popular assets of this type, in the search-result shape."""

    @abstractmethod
    def get_quote(self, ticker: str) -> Optional[dict]:
        """Full detail-page quote for one asset, or None if not found."""

    @abstractmethod
    def get_history(self, ticker: str) -> list[dict]:
        """A year of daily closes: [{'date': str, 'close': float}, ...]."""

    @abstractmethod
    def get_current_price(self, ticker: str) -> Decimal:
        """The price to execute a trade at right now. Raises if not found."""

    def can_trade(self, ticker: str) -> Tuple[bool, Optional[str]]:
        """Whether a new purchase of this ticker should be allowed. Defaults to yes."""
        return True, None


class StockProvider(AssetProvider):
    asset_type = 'stock'

    # Yahoo Finance exchange codes for Nasdaq, NYSE, and NYSE American/Arca.
    US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('exchange') in self.US_EXCHANGES

    def search(self, query: str) -> list[dict]:
        return _yfinance_search(query, self.matches_quote)

    def fetch_popular(self) -> list[dict]:
        results = yf.screen('most_actives')
        assets = []
        for quote in results.get('quotes', [])[:10]:
            assets.append({
                'symbol': quote['symbol'],
                'name': quote.get('shortName', 'N/A'),
                'currentPrice': quote.get('regularMarketPrice'),
                'volume': quote.get('regularMarketVolume'),
                'change': quote.get('regularMarketChange'),
                'changePercent': quote.get('regularMarketChangePercent'),
                'dayLow': quote.get('regularMarketDayLow'),
                'dayHigh': quote.get('regularMarketDayHigh'),
            })
        return assets

    def get_quote(self, ticker: str) -> Optional[dict]:
        return _yfinance_quote(ticker)

    def get_history(self, ticker: str) -> list[dict]:
        return _yfinance_history(ticker)

    def get_current_price(self, ticker: str) -> Decimal:
        return _yfinance_current_price(ticker)


class CryptoProvider(AssetProvider):
    asset_type = 'crypto'

    # Quote a fixed set of the largest cryptocurrencies by market cap directly.
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

    def search(self, query: str) -> list[dict]:
        return _yfinance_search(query, self.matches_quote)

    def fetch_popular(self) -> list[dict]:
        tickers = yf.Tickers(' '.join(self.POPULAR_SYMBOLS.keys()))
        assets = []
        for symbol, name in self.POPULAR_SYMBOLS.items():
            try:
                fast_info = tickers.tickers[symbol].fast_info
                assets.append({
                    'symbol': symbol,
                    'name': name,
                    'volume': fast_info.get('lastVolume'),
                    **_quote_fields(fast_info),
                })
            except Exception:
                continue
        return assets

    def get_quote(self, ticker: str) -> Optional[dict]:
        # yfinance treats crypto pairs the same as equities for quote/history purposes.
        return _yfinance_quote(ticker)

    def get_history(self, ticker: str) -> list[dict]:
        return _yfinance_history(ticker)

    def get_current_price(self, ticker: str) -> Decimal:
        return _yfinance_current_price(ticker)


class BondProvider(AssetProvider):
    asset_type = 'bond'

    def search(self, query: str) -> list[dict]:
        today = date.today()
        return [self._summary(bond, today) for bond in bond_pricing.search_bonds(query)]

    def fetch_popular(self) -> list[dict]:
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

    def get_history(self, ticker: str) -> list[dict]:
        bond = bond_pricing.get_bond(ticker)
        if bond is None:
            return []
        return bond_pricing.price_history(bond)

    def get_current_price(self, ticker: str) -> Decimal:
        bond = bond_pricing.get_bond(ticker)
        if bond is None:
            raise ValueError(f"Unknown bond ticker: {ticker}")
        return bond_pricing.price_bond(bond)

    def can_trade(self, ticker: str) -> Tuple[bool, Optional[str]]:
        bond = bond_pricing.get_bond(ticker)
        if bond is None:
            return False, 'Unknown bond ticker.'
        if bond_pricing.is_matured(bond):
            return False, 'This bond has matured.'
        return True, None


PROVIDERS: dict[str, AssetProvider] = {
    provider.asset_type: provider for provider in (StockProvider(), CryptoProvider(), BondProvider())
}
