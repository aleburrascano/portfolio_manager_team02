"""
Handle stock transactions in the database.
"""
import yfinance as yf


def purchaseStock(user_id: int, ticker: str, quantity: int, cursor, db) -> bool:
    """
    Purchases stock for the user.

    Args:
        user_id (int): The ID of the user.
        ticker (str): The stock ticker symbol.
        quantity (int): The number of shares to purchase.
        cursor: The database cursor.
        db: The database connection.

    Returns:
        bool: True if the purchase was successful, False otherwise.
    """
    try:
        # Get the current price of the stock
        stock = yf.Ticker(ticker)
        current_price = float(stock.history(period="1d")['Close'].iloc[0])

        # Insert the purchase into the database
        sql = "INSERT INTO stockTransactions (ticker, qty, price, val, stockTransactionType, userId) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (ticker, quantity, current_price, -abs(float(quantity) * current_price), "buy", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing stock purchase: {e}")
        return False


def sellStock(user_id: int, ticker: str, quantity: int, cursor, db) -> bool:
    """
    Sells stock for the user.

    Args:
        user_id (int): The ID of the user.
        ticker (str): The stock ticker symbol.
        quantity (int): The number of shares to sell.
        cursor: The database cursor.
        db: The database connection.

    Returns:
        bool: True if the sale was successful, False otherwise.
    """
    try:
        # Get the current price of the stock
        stock = yf.Ticker(ticker)
        current_price = float(stock.history(period="1d")['Close'].iloc[0])

        # Insert the sale into the database
        sql = "INSERT INTO stockTransactions (ticker, qty, price, val, stockTransactionType, userId) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (ticker, quantity, current_price, abs(float(quantity) * current_price), "sell", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing stock sale: {e}")
        return False