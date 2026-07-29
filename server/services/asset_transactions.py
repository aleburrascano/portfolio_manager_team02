"""
Buy and sell assets (stocks or crypto) for a user, priced from live
yfinance quotes.
"""
from decimal import Decimal
import yfinance as yf
import services.user_transactions as ut
import db.connection as db_conn

def get_holding_qty(user_id: int, ticker: str) -> float:
    """
    Get how many shares of an asset (stock or crypto) the user currently owns.

    Args:
        user_id (int): The ID of the user.
        ticker (str): The asset ticker symbol.

    Returns:
        float: The number of shares owned (0 if none or on connection failure).
    """
    return float(_get_holding_qty_decimal(user_id, ticker))

def _get_holding_qty_decimal(user_id: int, ticker: str) -> Decimal:
    db = db_conn.get_db()
    if db is None:
        return Decimal('0')

    cursor = db.cursor()
    cursor.execute(
        "SELECT SUM(qty) FROM AssetTransactions WHERE userId = %s AND ticker = %s",
        (user_id, ticker)
    )
    total_shares = cursor.fetchone()[0]
    cursor.close()
    return Decimal(total_shares) if total_shares is not None else Decimal('0')

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
    db = db_conn.get_db()
    if db is None: return False

    try:
        if not db_conn.lock_user(db, user_id):
            db.rollback()
            return False

        # Get the current price of the asset
        asset = yf.Ticker(ticker)
        current_price = Decimal(str(asset.history(period="1d")['Close'].iloc[0]))
        qty = Decimal(str(abs(quantity)))

        # Validate that the user has sufficient funds to make the purchase,
        # re-checked under the user row lock so no other request can race it
        cost = qty * current_price
        wallet = ut.get_user_balance(user_id)
        if wallet is None or wallet < cost:
            print(f"Insufficient funds for {asset_type} purchase.")
            db.rollback()
            return False

        # Insert the purchase into the database
        cursor = db.cursor()
        sql = "INSERT INTO AssetTransactions (assetType, ticker, qty, price, val, assetTransactionType, userId) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        val = (asset_type, ticker, qty, current_price, -cost, "buy", user_id)
        cursor.execute(sql, val)
        db.commit()
        cursor.close()
        return True
    except Exception as e:
        db.rollback()
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
    db = db_conn.get_db()
    if db is None: return False

    try:
        if not db_conn.lock_user(db, user_id):
            db.rollback()
            return False

        # Get the current price of the asset
        asset = yf.Ticker(ticker)
        current_price = Decimal(str(asset.history(period="1d")['Close'].iloc[0]))
        qty = Decimal(str(abs(quantity)))
        cost = qty * current_price

        # Validate that the user owns enough shares/units to sell, re-checked
        # under the user row lock so no other request can race it
        if _get_holding_qty_decimal(user_id, ticker) < qty:
            print(f"Insufficient holdings for {asset_type} sale.")
            db.rollback()
            return False

        # Insert the sale into the database
        cursor = db.cursor()
        sql = "INSERT INTO AssetTransactions (assetType, ticker, qty, price, val, assetTransactionType, userId) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        val = (asset_type, ticker, -qty, current_price, cost, "sell", user_id)
        cursor.execute(sql, val)
        db.commit()
        cursor.close()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error performing {asset_type} sale: {e}")
        return False
