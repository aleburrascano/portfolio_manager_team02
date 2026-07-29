"""
Per-asset-type behavior for the unified assets routes: what counts as a
valid search match, and which yfinance screener backs the "popular" list.
"""
from abc import ABC, abstractmethod
from typing import Optional


class AssetProvider(ABC):
    """Interface implemented by each supported asset type."""

    asset_type: str

    @abstractmethod
    def matches_quote(self, quote: dict) -> bool:
        """Whether a yfinance search quote belongs to this asset type."""

    @abstractmethod
    def popular_screener(self) -> Optional[str]:
        """yfinance predefined screener body for the 'popular' endpoint, or None."""


class StockProvider(AssetProvider):
    asset_type = 'stock'

    # Yahoo Finance exchange codes for Nasdaq, NYSE, and NYSE American/Arca.
    US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('exchange') in self.US_EXCHANGES

    def popular_screener(self) -> Optional[str]:
        return 'most_actives'


class CryptoProvider(AssetProvider):
    asset_type = 'crypto'

    def matches_quote(self, quote: dict) -> bool:
        return quote.get('quoteType') == 'CRYPTOCURRENCY'

    def popular_screener(self) -> Optional[str]:
        # yfinance has no stable predefined crypto screener; the popular
        # endpoint degrades gracefully to an empty list for this type.
        return None


PROVIDERS: dict[str, AssetProvider] = {
    provider.asset_type: provider for provider in (StockProvider(), CryptoProvider())
}
