"""
Per-asset-type behavior for the unified assets routes: what counts as a
valid search match, and what the "popular" list is made of.

Providers describe *which* assets belong to a type; services.market_data
does the fetching. Adding an asset type should mean adding a class here,
not touching the routes.
"""
from abc import ABC, abstractmethod
from typing import Dict, List

import services.market_data as market_data


class AssetProvider(ABC):
    """Interface implemented by each supported asset type."""

    asset_type: str

    @abstractmethod
    def matches_quote(self, quote: dict) -> bool:
        """Whether a market data search quote belongs to this asset type."""

    @abstractmethod
    def fetch_popular(self) -> List[dict]:
        """The top ~10 popular assets of this type, in the search-result shape."""


class StockProvider(AssetProvider):
    asset_type = 'stock'

    # Yahoo Finance exchange codes for Nasdaq, NYSE, and NYSE American/Arca.
    US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('exchange') in self.US_EXCHANGES

    def fetch_popular(self) -> List[dict]:
        return market_data.screen_most_active()


class CryptoProvider(AssetProvider):
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


PROVIDERS: Dict[str, AssetProvider] = {
    provider.asset_type: provider for provider in (StockProvider(), CryptoProvider())
}
