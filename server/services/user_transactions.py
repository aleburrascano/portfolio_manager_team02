"""
Read a user's combined cash and stock transaction history.
"""
from typing import Any, Dict, List, Optional
from db.connection import get_db

CASH_TRANSACTIONS_QUERY = (
    "SELECT cashTransactionId as transactionId, cashTransactionType as transactionType, "
    "amount, cashTransactionDate as transactionDate "
    "FROM CashTransactions WHERE userId = %s"
)

ASSET_TRANSACTIONS_QUERY = (
    "SELECT assetTransactionId as transactionId, assetTransactionType as transactionType, "
    "assetType, ticker, qty, price, val, assetTransactionDate as transactionDate "
    "FROM AssetTransactions WHERE userId = %s"
)


def get_user_transactions(user_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch a user's full transaction history (cash and stock), newest first.

    Args:
        user_id (int): The ID of the user.

    Returns:
        list[dict] | None: Combined transaction rows, each with a `signedAmount`
        field (positive = cash in, negative = cash out), or None if the
        database connection failed.
    """
    conn = get_db()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)

    cursor.execute(CASH_TRANSACTIONS_QUERY, (user_id,))
    cash_rows = cursor.fetchall()
    for row in cash_rows:
        row['type'] = 'cash'
        row['signedAmount'] = row['amount']

    cursor.execute(ASSET_TRANSACTIONS_QUERY, (user_id,))
    asset_rows = cursor.fetchall()
    for row in asset_rows:
        row['type'] = row['assetType']
        row['signedAmount'] = row['val']

    cursor.close()

    transactions = cash_rows + asset_rows
    transactions.sort(key=lambda row: row['transactionDate'], reverse=True)
    return transactions


def get_user_balance(user_id: int) -> Optional[float]:
    """
    Compute a user's net cash balance across all cash and stock transactions.

    Args:
        user_id (int): The ID of the user.

    Returns:
        float | None: The net balance, or None if the database connection failed.
    """
    transactions = get_user_transactions(user_id)
    if transactions is None:
        return None
    return sum(row['signedAmount'] for row in transactions)
