"""
Deposit and withdraw cash for a user's wallet balance.
"""
from decimal import Decimal

import db.connection as db_conn
import services.user_transactions as ut
from db.models import CashTransaction
from services.exceptions import InsufficientFunds, UnknownUser


def deposit_cash(user_id: int, amount: float) -> None:
    """
    Deposit cash into the user's account.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to deposit.
    """
    session = db_conn.get_session()
    try:
        session.add(CashTransaction(
            cashTransactionType='deposit',
            amount=abs(Decimal(str(amount))),
            userId=user_id,
        ))
        session.commit()
    except Exception:
        session.rollback()
        raise


def withdraw_cash(user_id: int, amount: float) -> None:
    """
    Withdraw cash from the user's account, provided the balance covers it.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to withdraw.

    Raises:
        UnknownUser: if no such user exists.
        InsufficientFunds: if the balance doesn't cover the withdrawal.
    """
    session = db_conn.get_session()

    try:
        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        # Re-checked under the user row lock, so no concurrent request can
        # withdraw the same balance twice.
        withdrawal = abs(Decimal(str(amount)))
        if ut.get_user_balance(user_id) < withdrawal:
            raise InsufficientFunds('Not enough cash for this withdrawal.')

        session.add(CashTransaction(
            cashTransactionType='withdraw',
            amount=-withdrawal,
            userId=user_id,
        ))
        session.commit()
    except Exception:
        session.rollback()
        raise
