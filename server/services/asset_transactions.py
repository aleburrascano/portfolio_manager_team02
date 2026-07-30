"""
Buy and sell assets (stocks, crypto, or bonds) for a user, priced through
each asset type's AssetProvider.
"""
from decimal import Decimal

from sqlalchemy import func, select

import db.connection as db_conn
import services.user_transactions as ut
from db.models import Asset, AssetTransaction
from services.asset_providers import PROVIDERS
from services.exceptions import (
    InsufficientFunds, InsufficientHoldings, InvalidInput, UnknownUser,
)


def _register_asset(session, ticker: str, asset_type: str) -> None:
    """
    Make sure the asset exists before a transaction references it.

    The Assets row is what says a ticker is a stock, a crypto or a bond, so
    it has to be there before the foreign key from the trade can point at it.
    """
    if session.get(Asset, ticker) is None:
        session.add(Asset(ticker=ticker, assetType=asset_type))
        session.flush()


def get_holding_qty(user_id: int, ticker: str) -> float:
    """
    Get how many shares/units of an asset the user currently owns.

    Args:
        user_id (int): The ID of the user.
        ticker (str): The asset ticker symbol.

    Returns:
        float: The number of shares owned (0 if none).
    """
    return float(_get_holding_qty_decimal(user_id, ticker))


def _get_holding_qty_decimal(user_id: int, ticker: str) -> Decimal:
    total_shares = db_conn.get_session().scalar(
        select(func.coalesce(func.sum(AssetTransaction.qty), 0))
        .where(AssetTransaction.userId == user_id, AssetTransaction.ticker == ticker)
    )
    return Decimal(str(total_shares))


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
        # Asked before anything is locked or priced, so a bond that has
        # matured is refused with its own reason rather than a stale price.
        tradable, reason = provider.can_trade(ticker)
        if not tradable:
            raise InvalidInput(reason or 'This asset cannot be bought.')

        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        price = provider.trade_price(ticker)
        cost = quantity * price

        # Re-checked under the user row lock, so no concurrent request can
        # spend the same balance twice.
        if ut.get_user_balance(user_id) < cost:
            raise InsufficientFunds('Not enough cash for this purchase.')

        _register_asset(session, ticker, asset_type)
        session.add(AssetTransaction(
            ticker=ticker,
            qty=quantity,
            price=price,
            assetTransactionType='buy',
            userId=user_id,
        ))
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

        price = provider.trade_price(ticker)

        # Re-checked under the user row lock, so no concurrent request can
        # sell the same shares twice.
        if _get_holding_qty_decimal(user_id, ticker) < quantity:
            raise InsufficientHoldings('Not enough shares to sell.')

        _register_asset(session, ticker, asset_type)
        session.add(AssetTransaction(
            ticker=ticker,
            qty=-quantity,
            price=price,
            assetTransactionType='sell',
            userId=user_id,
        ))
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

    totals = {asset_type: 0.0 for asset_type in PROVIDERS}
    for asset_type, ticker, qty in holdings:
        if qty and asset_type in totals:
            totals[asset_type] += float(qty) * PROVIDERS[asset_type].valuation_price(ticker)

    return {'cash': float(ut.get_user_balance(user_id)), **totals}
