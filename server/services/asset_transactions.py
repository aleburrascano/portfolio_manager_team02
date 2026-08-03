"""
Buy and sell assets (stocks, crypto, or bonds) for a user, priced through
each asset type's AssetProvider.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict

from sqlalchemy import func, select

import db.connection as db_conn
import services.user_transactions as ut
from db.models import Asset, AssetTransaction
from services.asset_providers import PROVIDERS
from services.exceptions import (
    InsufficientFunds, InsufficientHoldings, InvalidInput, UnknownUser,
)


def register_asset(session, provider, ticker: str) -> None:
    """
    Make sure the asset exists, and is the type it claims to be, before a
    transaction references it.

    The Assets row is what says a ticker is a stock, a crypto or a bond, and
    it's what the portfolio breakdown groups by - so getting it wrong
    misfiles that asset for every trade that follows. It's therefore checked
    twice: a new ticker is confirmed with the provider before being
    recorded, and a known one keeps the type it was first filed under.

    The provider lookup only happens the first time a ticker is ever traded,
    so the cost isn't paid on the hot path.

    Raises:
        InvalidInput: if the ticker isn't this type of asset.
    """
    existing = session.get(Asset, ticker)
    if existing is None:
        if provider.owns_ticker(ticker) is False:
            raise InvalidInput(f'{ticker} is not a {provider.asset_type}.')
        session.add(Asset(ticker=ticker, assetType=provider.asset_type))
        session.flush()
    elif existing.assetType != provider.asset_type:
        raise InvalidInput(f'{ticker} is a {existing.assetType}, not a {provider.asset_type}.')


def get_holding_qty(user_id: int, ticker: str) -> float:
    """
    Get how many shares/units of an asset the user currently owns.

    Args:
        user_id (int): The ID of the user.
        ticker (str): The asset ticker symbol.

    Returns:
        float: The number of shares owned (0 if none).
    """
    return float(get_holding_qty_decimal(user_id, ticker))


def get_holding_qty_decimal(user_id: int, ticker: str) -> Decimal:
    total_shares = db_conn.get_session().scalar(
        select(func.coalesce(func.sum(AssetTransaction.qty), 0))
        .where(AssetTransaction.userId == user_id, AssetTransaction.ticker == ticker)
    )
    return Decimal(str(total_shares))


def record_trade(
    session, user_id: int, ticker: str, quantity: Decimal, price: Decimal, side: str
) -> AssetTransaction:
    """
    Insert the one AssetTransaction row a trade produces, signed by side.

    Shared by purchase_asset/sell_asset (market orders) and
    services.limit_orders (the fill a pending order produces), so there is
    exactly one place that builds an AssetTransaction and exactly one shape
    it can have.
    """
    tx = AssetTransaction(
        ticker=ticker,
        qty=quantity if side == 'buy' else -quantity,
        price=price,
        assetTransactionType=side,
        userId=user_id,
    )
    session.add(tx)
    session.flush()
    return tx


def purchase_asset(user_id: int, asset_type: str, ticker: str, quantity: Decimal) -> None:
    """
    Purchase an asset for the user, at the current market price, provided
    their wallet covers it and the asset is still tradable.

    Args:
        user_id (int): The ID of the user.
        asset_type (str): 'stock', 'crypto', or 'bond'.
        ticker (str): The asset ticker symbol.
        quantity (Decimal): The number of shares/units to purchase. Validated positive.

    Raises:
        UnknownUser: if no such user exists.
        InvalidInput: if the asset can't be bought (an unknown or matured bond).
        MarketDataUnavailable: if the asset can't be priced.
        InsufficientFunds: if the wallet doesn't cover the purchase.
    """
    provider = PROVIDERS[asset_type]
    session = db_conn.get_session()

    try:
        tradable, reason = provider.can_trade(ticker)
        if not tradable:
            raise InvalidInput(reason or 'This asset cannot be bought.')

        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        register_asset(session, provider, ticker)
        price = provider.trade_price(ticker)
        cost = quantity * price

        if ut.get_user_balance(user_id) < cost:
            raise InsufficientFunds('Not enough cash for this purchase.')

        record_trade(session, user_id, ticker, quantity, price, 'buy')
        session.commit()
    except Exception:
        session.rollback()
        raise


def sell_asset(user_id: int, asset_type: str, ticker: str, quantity: Decimal) -> None:
    """
    Sell an asset for the user, at the current market price, provided they
    hold enough of it.

    Selling is deliberately not gated on can_trade: a holding should stay
    disposable even once the asset stops being available to buy.

    Args:
        user_id (int): The ID of the user.
        asset_type (str): 'stock', 'crypto', or 'bond'.
        ticker (str): The asset ticker symbol.
        quantity (Decimal): The number of shares/units to sell. Validated positive.

    Raises:
        UnknownUser: if no such user exists.
        MarketDataUnavailable: if the asset can't be priced.
        InsufficientHoldings: if the user doesn't hold that many units.
    """
    provider = PROVIDERS[asset_type]
    session = db_conn.get_session()

    try:
        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        register_asset(session, provider, ticker)
        price = provider.trade_price(ticker)

        if get_holding_qty_decimal(user_id, ticker) < quantity:
            raise InsufficientHoldings('Not enough shares to sell.')

        record_trade(session, user_id, ticker, quantity, price, 'sell')
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_portfolio_values(user_id: int) -> dict:
    """
    Compute the portfolio breakdown for a user.

    Returns a dict with a key per asset type plus 'cash', each holding the
    current total value for that category. The buckets come from the
    provider registry, so a new asset type shows up here on its own. Cash is
    the user's net wallet balance; asset values are current prices times net
    holdings.
    """
    session = db_conn.get_session()

    holdings = session.execute(
        select(Asset.assetType, AssetTransaction.ticker, func.sum(AssetTransaction.qty))
        .join(Asset, Asset.ticker == AssetTransaction.ticker)
        .where(AssetTransaction.userId == user_id)
        .group_by(Asset.assetType, AssetTransaction.ticker)
    ).all()

    held: Dict[str, Dict[str, float]] = defaultdict(dict)
    for asset_type, ticker, qty in holdings:
        if qty and asset_type in PROVIDERS:
            held[asset_type][ticker] = float(qty)

    totals = {asset_type: 0.0 for asset_type in PROVIDERS}
    for asset_type, quantities in held.items():
        prices = PROVIDERS[asset_type].valuation_prices(list(quantities))
        for ticker, qty in quantities.items():
            totals[asset_type] += qty * prices.get(ticker, 0.0)

    return {'cash': float(ut.get_user_balance(user_id)), **totals}
