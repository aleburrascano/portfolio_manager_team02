"""
Handle cash transactions in the database.
"""

def depositCash(user_id: int, amount: float, cursor, db) -> bool:
    """
    Deposits cash into the user's account.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to deposit.
        cursor: The database cursor.
        db: The database connection.

    Returns:
        bool: True if the deposit was successful, False otherwise.
    """
    try:
        sql = "INSERT INTO cashTransactions (amount, cashTransactionType, userId) VALUES (%s, %s, %s)"
        val = (abs(amount), "deposit", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing cash deposit: {e}")
        return False


def withdrawCash(user_id: int, amount: float, cursor, db) -> bool:
    """
    Withdraws cash from the user's account.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to withdraw.
        cursor: The database cursor.
        db: The database connection.

    Returns:
        bool: True if the withdrawal was successful, False otherwise.
    """
    try:
        sql = "INSERT INTO cashTransactions (amount, cashTransactionType, userId) VALUES (%s, %s, %s)"
        val = (-abs(amount), "withdraw", user_id)
        cursor.execute(sql, val)
        db.commit()
        return True
    except Exception as e:
        print(f"Error performing cash withdrawal: {e}")
        return False