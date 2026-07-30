"""
Buy and sell assets (stocks or crypto) for a user, priced from live
yfinance quotes.
"""
from decimal import Decimal

import yfinance as yf
from sqlalchemy import func, select

import db.connection as db_conn
import services.user_transactions as ut
from db.models import AssetTransaction

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

def purchase_asset(user_id: int, asset_type: str, ticker: str, quantity: float) -> bool:
    """
    Purchases an asset (stock or crypto) for the user. Make sure that the
    user has sufficient funds to make the purchase before proceeding.

    Args:
        user_id (int): The ID of the user.
        asset_type (str): 'stock' or 'crypto'.
        ticker (str): The asset ticker symbol.
        quantity (float): The number of shares/units to purchase.

    Returns:
        bool: True if the purchase was successful, False otherwise.
    """
    session = db_conn.get_session()

    try:
        if not db_conn.lock_user(session, user_id):
            session.rollback()
            return False

        # Get the current price of the asset
        asset = yf.Ticker(ticker)
        current_price = Decimal(str(asset.history(period="1d")['Close'].iloc[0]))
        qty = Decimal(str(abs(quantity)))

        # Validate that the user has sufficient funds to make the purchase,
        # re-checked under the user row lock so no other request can race it
        cost = qty * current_price
        if ut.get_user_balance(user_id) < cost:
            print(f"Insufficient funds for {asset_type} purchase.")
            session.rollback()
            return False

        session.add(AssetTransaction(
            assetType=asset_type,
            ticker=ticker,
            qty=qty,
            price=current_price,
            val=-cost,
            assetTransactionType='buy',
            userId=user_id,
        ))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error performing {asset_type} purchase: {e}")
        return False


def sell_asset(user_id: int, asset_type: str, ticker: str, quantity: float) -> bool:
    """
    Sells an asset (stock or crypto) for the user. Make sure that the user
    owns enough shares/units to sell before proceeding.

    Args:
        user_id (int): The ID of the user.
        asset_type (str): 'stock' or 'crypto'.
        ticker (str): The asset ticker symbol.
        quantity (float): The number of shares/units to sell.

    Returns:
        bool: True if the sale was successful, False otherwise.
    """
    session = db_conn.get_session()

    try:
        if not db_conn.lock_user(session, user_id):
            session.rollback()
            return False

        # Get the current price of the asset
        asset = yf.Ticker(ticker)
        current_price = Decimal(str(asset.history(period="1d")['Close'].iloc[0]))
        qty = Decimal(str(abs(quantity)))
        proceeds = qty * current_price

        # Validate that the user owns enough shares/units to sell, re-checked
        # under the user row lock so no other request can race it
        if _get_holding_qty_decimal(user_id, ticker) < qty:
            print(f"Insufficient holdings for {asset_type} sale.")
            session.rollback()
            return False

        session.add(AssetTransaction(
            assetType=asset_type,
            ticker=ticker,
            qty=-qty,
            price=current_price,
            val=proceeds,
            assetTransactionType='sell',
            userId=user_id,
        ))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error performing {asset_type} sale: {e}")
        return False



def get_portfolio_values(user_id: int) -> dict:
    """
    Compute the portfolio breakdown for a user.

    Returns a dict with keys 'cash', 'stock', and 'crypto' representing
    the current total value for each category. Cash is taken from the
    user's net wallet balance (cash + asset transaction effects). Asset
    values are computed from current prices multiplied by net holdings.
    """
    session = db_conn.get_session()
    cash = ut.get_user_balance(user_id)

    rows = session.execute(
        select(AssetTransaction.assetType, AssetTransaction.ticker, func.sum(AssetTransaction.qty))
        .where(AssetTransaction.userId == user_id)
        .group_by(AssetTransaction.assetType, AssetTransaction.ticker)
    ).all()

    totals = {'stock': 0.0, 'crypto': 0.0}

    for asset_type, ticker, qty in rows:
        if not qty:
            continue

        price = 0.0
        try:
            asset = yf.Ticker(ticker)
            fast_info = getattr(asset, 'fast_info', None) or {}
            last_price = fast_info.get('lastPrice')
            if last_price is not None:
                price = float(last_price)
            else:
                price = float(asset.history(period="1d")['Close'].iloc[0])
        except Exception:
            price = 0.0

        totals[asset_type] += float(qty) * price

    return {'cash': float(cash), 'stock': totals['stock'], 'crypto': totals['crypto']}
