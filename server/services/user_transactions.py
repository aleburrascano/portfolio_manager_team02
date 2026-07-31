"""
Read a user's combined cash and asset transaction history.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import String, cast, func, literal, select, union_all

from db.connection import get_session
from db.models import MONEY, Asset, AssetTransaction, CashTransaction

# The cash effect of a trade: negative when buying (qty is positive),
# positive when selling (qty is negative). Derived rather than stored, so
# it can never disagree with the quantity and price it comes from.
CASH_EFFECT = -AssetTransaction.qty * AssetTransaction.price


def get_user_transactions(
    user_id: int, limit: Optional[int] = None, offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Fetch a user's transaction history (cash and asset), newest first.

    The two tables are combined with UNION ALL rather than being merged in
    Python, so the sort and any limit happen in the database against an
    index instead of pulling the user's whole history into memory.

    Args:
        user_id (int): The ID of the user.
        limit (int | None): Maximum rows to return, or None for all of them.
        offset (int): Rows to skip, for paging through the history.

    Returns:
        list[dict]: Transaction rows, each with a `signedAmount` field
        (positive = cash in, negative = cash out).
    """
    # A UNION takes each column's type from its first branch, so the two
    # transaction-type enums are cast to plain text - otherwise 'buy' comes
    # back through the cash enum and fails to load.
    cash = select(
        CashTransaction.cashTransactionId.label('transactionId'),
        literal('cash', String).label('type'),
        cast(CashTransaction.cashTransactionType, String).label('transactionType'),
        literal(None, String).label('ticker'),
        literal(None, MONEY).label('qty'),
        literal(None, MONEY).label('price'),
        CashTransaction.amount.label('signedAmount'),
        CashTransaction.cashTransactionDate.label('transactionDate'),
    ).where(CashTransaction.userId == user_id)

    assets = select(
        AssetTransaction.assetTransactionId,
        cast(Asset.assetType, String),
        cast(AssetTransaction.assetTransactionType, String),
        AssetTransaction.ticker,
        AssetTransaction.qty,
        AssetTransaction.price,
        CASH_EFFECT,
        AssetTransaction.assetTransactionDate,
    ).join(Asset, Asset.ticker == AssetTransaction.ticker).where(
        AssetTransaction.userId == user_id
    )

    combined = union_all(cash, assets).subquery()
    statement = select(combined).order_by(combined.c.transactionDate.desc())
    if limit is not None:
        statement = statement.limit(limit).offset(offset)

    return [dict(row) for row in get_session().execute(statement).mappings()]


def get_user_balance(user_id: int) -> Decimal:
    """
    Compute a user's net cash balance across all cash and asset transactions.

    Args:
        user_id (int): The ID of the user.

    Returns:
        Decimal: The net balance (0 if the user has no transactions).
    """
    transactions = get_user_transactions(user_id)
    if transactions is None:
        return None
    return sum(row['signedAmount'] for row in transactions)

def get_user_asset_transactions(user_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch only a user's asset transactions.

    Returns:
        list[dict] | None: Asset transactions for the user.
    """

    conn = get_db()

    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)

    cursor.execute(ASSET_TRANSACTIONS_QUERY, (user_id,))
    asset_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    for row in asset_rows:
        row["type"] = row["assetType"]
        row["signedAmount"] = row["val"]

    asset_rows.sort(
        key=lambda row: row["transactionDate"],
        reverse=True
    )

    return asset_rows


  ''' session = get_session()

  cash = session.scalar(
        select(func.coalesce(func.sum(CashTransaction.amount), 0))
        .where(CashTransaction.userId == user_id)
    )
    assets = session.scalar(
        select(func.coalesce(func.sum(CASH_EFFECT), 0))
        .where(AssetTransaction.userId == user_id)
    )
    return Decimal(str(cash)) + Decimal(str(assets))
    '''
