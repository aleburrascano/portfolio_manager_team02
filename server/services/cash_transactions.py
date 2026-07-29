"""
Deposit and withdraw cash for a user's wallet balance.
"""
import services.user_transactions as ut
import db.connection as db_conn

def deposit_cash(user_id: int, amount: float) -> bool:
    """
    Deposits cash into the user's account. Ensure that the amount is 
    positive before proceeding with the deposit.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to deposit.
        cursor: The database cursor.
        db: The database connection.

    Returns:
        bool: True if the deposit was successful, False otherwise.
    """
    try:
        db = db_conn.get_db()
        if db is None: return False
        cursor = db.cursor()
        
        # Validate that the amount is positive and insert into the database
        sql = "INSERT INTO CashTransactions (amount, cashTransactionType, userId) VALUES (%s, %s, %s)"
        val = (abs(amount), "deposit", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing cash deposit: {e}")
        return False


def withdraw_cash(user_id: int, amount: float) -> bool:
    """
    Withdraws cash from the user's account. Ensure that the provided amount 
    is positive before proceeding with the withdrawal, and that the user has 
    sufficient funds.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to withdraw.
        cursor: The database cursor.
        db: The database connection.

    Returns:
        bool: True if the withdrawal was successful, False otherwise.
    """
    db = db_conn.get_db()
    if db is None: return False

    try:
        if not db_conn.lock_user(db, user_id):
            db.rollback()
            return False

        # Validate that the user has sufficient funds to make the withdrawal,
        # re-checked under the user row lock so no other request can race it
        wallet = ut.get_user_balance(user_id)
        if wallet is None or wallet < abs(amount):
            print("Insufficient funds for withdrawal.")
            db.rollback()
            return False

        # Insert the withdrawal into the database
        cursor = db.cursor()
        sql = "INSERT INTO CashTransactions (amount, cashTransactionType, userId) VALUES (%s, %s, %s)"
        val = (-abs(amount), "withdraw", user_id)
        cursor.execute(sql, val)
        db.commit()
        cursor.close()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error performing cash withdrawal: {e}")
        return False