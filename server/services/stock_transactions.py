"""
Buy and sell stock for a user, priced from live yfinance quotes.
"""
import yfinance as yf
import services.user_transactions as ut
import db.connection as db_conn

def purchase_stock(user_id: int, ticker: str, quantity: int) -> bool:
    """
    Purchases stock for the user. Make sure that the user has sufficient 
    funds to make the purchase before proceeding.

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
        db = db_conn.get_db()
        if db is None: return False
        cursor = db.cursor() 

        # Get the current price of the stock
        stock = yf.Ticker(ticker)
        current_price = float(stock.history(period="1d")['Close'].iloc[0])

        # Validate that the user has sufficient funds to make the purchase
        cost = abs(float(quantity) * current_price)
        wallet = ut.get_user_balance(user_id)
        if wallet is None or wallet < cost:
            print("Insufficient funds for stock purchase.")
            return False

        # Insert the purchase into the database
        sql = "INSERT INTO StockTransactions (ticker, qty, price, val, stockTransactionType, userId) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (ticker, abs(quantity), current_price, -cost, "buy", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing stock purchase: {e}")
        return False


def sell_stock(user_id: int, ticker: str, quantity: int) -> bool:
    """
    Sells stock for the user. Make sure that the user owns enough 
    shares of the stock to sell before proceeding.

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
        db = db_conn.get_db()
        if db is None: return False
        cursor = db.cursor()
        
        # Get the current price of the stock
        stock = yf.Ticker(ticker)
        current_price = float(stock.history(period="1d")['Close'].iloc[0])
        cost = abs(float(quantity) * current_price)

        # Validate that the user owns enough shares to sell
        sql = "SELECT SUM(qty) FROM StockTransactions WHERE userId = %s AND ticker = %s"
        cursor.execute(sql, (user_id, ticker))
        total_shares = cursor.fetchone()[0]
        if total_shares is None or total_shares < quantity:
            print("Insufficient shares for sale.")
            return False

        # Insert the sale into the database
        sql = "INSERT INTO StockTransactions (ticker, qty, price, val, stockTransactionType, userId) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (ticker, -abs(quantity), current_price, cost, "sell", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing stock sale: {e}")
        return False