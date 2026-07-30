"""
Read a user's combined cash and asset transaction history.
"""
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import func, select

from db.connection import get_session
from db.models import AssetTransaction, CashTransaction


def get_user_transactions(user_id: int) -> List[Dict[str, Any]]:
    """
    Fetch a user's full transaction history (cash and asset), newest first.

    Args:
        user_id (int): The ID of the user.

    Returns:
        list[dict]: Combined transaction rows, each with a `signedAmount`
        field (positive = cash in, negative = cash out).
    """
    session = get_session()

    cash_rows = [
        {
            'transactionId': row.cashTransactionId,
            'transactionType': row.cashTransactionType,
            'amount': row.amount,
            'transactionDate': row.cashTransactionDate,
            'type': 'cash',
            'signedAmount': row.amount,
        }
        for row in session.scalars(
            select(CashTransaction).where(CashTransaction.userId == user_id)
        )
    ]

    asset_rows = [
        {
            'transactionId': row.assetTransactionId,
            'transactionType': row.assetTransactionType,
            'assetType': row.assetType,
            'ticker': row.ticker,
            'qty': row.qty,
            'price': row.price,
            'val': row.val,
            'transactionDate': row.assetTransactionDate,
            'type': row.assetType,
            'signedAmount': row.val,
        }
        for row in session.scalars(
            select(AssetTransaction).where(AssetTransaction.userId == user_id)
        )
    ]

    transactions = cash_rows + asset_rows
    transactions.sort(key=lambda row: row['transactionDate'], reverse=True)
    return transactions


def get_user_balance(user_id: int) -> Decimal:
    """
    Compute a user's net cash balance across all cash and asset transactions.

    Args:
        user_id (int): The ID of the user.

    Returns:
        Decimal: The net balance (0 if the user has no transactions).
    """
    session = get_session()

    cash = session.scalar(
        select(func.coalesce(func.sum(CashTransaction.amount), 0))
        .where(CashTransaction.userId == user_id)
    )
    assets = session.scalar(
        select(func.coalesce(func.sum(AssetTransaction.val), 0))
        .where(AssetTransaction.userId == user_id)
    )
    return Decimal(str(cash)) + Decimal(str(assets))
