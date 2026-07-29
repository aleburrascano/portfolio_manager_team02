"""
Per-asset-type behavior for the unified assets routes: what counts as a
valid search match, and how to build the "popular" list.
"""
from abc import ABC, abstractmethod
import yfinance as yf


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


class AssetProvider(ABC):
    """Interface implemented by each supported asset type."""

    asset_type: str

    @abstractmethod
    def matches_quote(self, quote: dict) -> bool:
        """Whether a yfinance search quote belongs to this asset type."""

    @abstractmethod
    def fetch_popular(self) -> list[dict]:
        """The top ~10 popular assets of this type, in the search-result shape."""


class StockProvider(AssetProvider):
    asset_type = 'stock'

    # Yahoo Finance exchange codes for Nasdaq, NYSE, and NYSE American/Arca.
    US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('exchange') in self.US_EXCHANGES

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


class CryptoProvider(AssetProvider):
    asset_type = 'crypto'

    # yfinance's screener only supports equities/funds/ETFs, so there's no
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


PROVIDERS: dict[str, AssetProvider] = {
    provider.asset_type: provider for provider in (StockProvider(), CryptoProvider())
}
