"""
Read a user's combined cash and asset transaction history.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import String, cast, func, literal, select, union_all

from db.connection import get_session
from db.models import MONEY, Asset, AssetTransaction, CashTransaction

CASH_EFFECT = -AssetTransaction.qty * AssetTransaction.price


def get_user_transactions(
    user_id: int, limit: Optional[int] = None, offset: int = 0, newest_first: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch a user's transaction history (cash and asset).

    The two tables are combined with UNION ALL rather than being merged in
    Python, so the sort and any limit happen in the database against an
    index instead of pulling the user's whole history into memory.

    The sort direction is a parameter rather than the caller's job for the
    same reason the limit is: reversing a page in the client would only
    reverse the rows that page happens to hold, which is not the same list.

    Args:
        user_id (int): The ID of the user.
        limit (int | None): Maximum rows to return, or None for all of them.
        offset (int): Rows to skip, for paging through the history.
        newest_first (bool): Sort direction.

    Returns:
        list[dict]: Transaction rows, each with a `signedAmount` field
        (positive = cash in, negative = cash out).
    """
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
    ordering = combined.c.transactionDate.desc() if newest_first else combined.c.transactionDate.asc()
    statement = select(combined).order_by(ordering)
    if limit is not None:
        statement = statement.limit(limit).offset(offset)

    return [dict(row) for row in get_session().execute(statement).mappings()]


def count_user_transactions(user_id: int) -> int:
    """
    How many rows a user's history has, cash and asset together.

    Counted in the database rather than by measuring a fetched list, so a
    caller asking for one page can still say how many pages there are
    without pulling the other ones to find out.
    """
    session = get_session()
    cash = session.scalar(
        select(func.count()).select_from(CashTransaction)
        .where(CashTransaction.userId == user_id)
    )
    assets = session.scalar(
        select(func.count()).select_from(AssetTransaction)
        .where(AssetTransaction.userId == user_id)
    )
    return int(cash or 0) + int(assets or 0)


def get_user_balance(user_id: int) -> Decimal:
    """
    Compute a user's net cash balance across all cash and asset transactions.

    Summed in the database rather than by pulling the history into Python:
    the balance is re-checked under a row lock on every trade, so it sits on
    the hot path and must not scale with how long a user has been trading.

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
        select(func.coalesce(func.sum(CASH_EFFECT), 0))
        .where(AssetTransaction.userId == user_id)
    )
    return Decimal(str(cash)) + Decimal(str(assets))


def get_user_asset_transactions(user_id: int) -> List[Dict[str, Any]]:
    """
    Fetch a user's asset trades only, oldest first, with the asset type
    each ticker is filed under.

    Oldest first because the callers - performance and cost basis - replay
    the trades forward from the first one.

    Note that `qty` is already signed in this schema: positive on a buy,
    negative on a sell. Running totals can therefore be summed directly
    without re-deriving a sign from the transaction type.

    Args:
        user_id (int): The ID of the user.

    Returns:
        list[dict]: Rows of transactionId, ticker, assetType, qty, price,
        transactionDate.
    """
    statement = (
        select(
            AssetTransaction.assetTransactionId.label('transactionId'),
            AssetTransaction.ticker,
            cast(Asset.assetType, String).label('assetType'),
            AssetTransaction.qty,
            AssetTransaction.price,
            AssetTransaction.assetTransactionDate.label('transactionDate'),
        )
        .join(Asset, Asset.ticker == AssetTransaction.ticker)
        .where(AssetTransaction.userId == user_id)
        .order_by(AssetTransaction.assetTransactionDate.asc())
    )
    return [dict(row) for row in get_session().execute(statement).mappings()]


def get_cash_flows(user_id: int) -> List[Dict[str, Any]]:
    """
    A user's deposits and withdrawals, oldest first.

    Performance is measured against money the user actually put in, so the
    cash ledger is needed separately from the trades that move it around.

    Args:
        user_id (int): The ID of the user.

    Returns:
        list[dict]: Rows of amount (signed) and transactionDate.
    """
    statement = (
        select(
            CashTransaction.amount,
            CashTransaction.cashTransactionDate.label('transactionDate'),
        )
        .where(CashTransaction.userId == user_id)
        .order_by(CashTransaction.cashTransactionDate.asc())
    )
    return [dict(row) for row in get_session().execute(statement).mappings()]
