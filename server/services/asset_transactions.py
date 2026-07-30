"""
Buy and sell assets (stocks or crypto) for a user, priced from live
market data.
"""
from decimal import Decimal

from sqlalchemy import func, select

import db.connection as db_conn
import services.market_data as market_data
import services.user_transactions as ut
from db.models import AssetTransaction
from services.exceptions import InsufficientFunds, InsufficientHoldings, UnknownUser


def get_holding_qty(user_id: int, ticker: str) -> float:
    """
    Get how many shares of an asset (stock or crypto) the user currently owns.

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


def purchase_asset(user_id: int, asset_type: str, ticker: str, quantity: float) -> None:
    """
    Purchase an asset (stock or crypto) for the user, at the current market
    price, provided their wallet covers it.

    Args:
        user_id (int): The ID of the user.
        asset_type (str): 'stock' or 'crypto'.
        ticker (str): The asset ticker symbol.
        quantity (float): The number of shares/units to purchase.

    Raises:
        UnknownUser: if no such user exists.
        MarketDataUnavailable: if the asset can't be priced.
        InsufficientFunds: if the wallet doesn't cover the purchase.
    """
    session = db_conn.get_session()

    try:
        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        price = market_data.trade_price(ticker)
        qty = Decimal(str(abs(quantity)))
        cost = qty * price

        # Re-checked under the user row lock, so no concurrent request can
        # spend the same balance twice.
        if ut.get_user_balance(user_id) < cost:
            raise InsufficientFunds('Not enough cash for this purchase.')

        session.add(AssetTransaction(
            assetType=asset_type,
            ticker=ticker,
            qty=qty,
            price=price,
            val=-cost,
            assetTransactionType='buy',
            userId=user_id,
        ))
        session.commit()
    except Exception:
        session.rollback()
        raise


def sell_asset(user_id: int, asset_type: str, ticker: str, quantity: float) -> None:
    """
    Sell an asset (stock or crypto) for the user, at the current market
    price, provided they hold enough of it.

    Args:
        user_id (int): The ID of the user.
        asset_type (str): 'stock' or 'crypto'.
        ticker (str): The asset ticker symbol.
        quantity (float): The number of shares/units to sell.

    Raises:
        UnknownUser: if no such user exists.
        MarketDataUnavailable: if the asset can't be priced.
        InsufficientHoldings: if the user doesn't hold that many units.
    """
    session = db_conn.get_session()

    try:
        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        price = market_data.trade_price(ticker)
        qty = Decimal(str(abs(quantity)))
        proceeds = qty * price

        # Re-checked under the user row lock, so no concurrent request can
        # sell the same shares twice.
        if _get_holding_qty_decimal(user_id, ticker) < qty:
            raise InsufficientHoldings('Not enough shares to sell.')

        session.add(AssetTransaction(
            assetType=asset_type,
            ticker=ticker,
            qty=-qty,
            price=price,
            val=proceeds,
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

    Returns a dict with keys 'cash', 'stock', and 'crypto' representing
    the current total value for each category. Cash is taken from the
    user's net wallet balance (cash + asset transaction effects). Asset
    values are current prices multiplied by net holdings.
    """
    session = db_conn.get_session()

    holdings = session.execute(
        select(AssetTransaction.assetType, AssetTransaction.ticker, func.sum(AssetTransaction.qty))
        .where(AssetTransaction.userId == user_id)
        .group_by(AssetTransaction.assetType, AssetTransaction.ticker)
    ).all()

    totals = {'stock': 0.0, 'crypto': 0.0}
    for asset_type, ticker, qty in holdings:
        if qty:
            totals[asset_type] += float(qty) * market_data.valuation_price(ticker)

    return {'cash': float(ut.get_user_balance(user_id)), **totals}
