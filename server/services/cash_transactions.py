"""
Deposit and withdraw cash for a user's wallet balance.
"""
from decimal import Decimal

import db.connection as db_conn
import services.user_transactions as ut
from db.models import CashTransaction


def deposit_cash(user_id: int, amount: float) -> bool:
    """
    Deposits cash into the user's account. Ensure that the amount is
    positive before proceeding with the deposit.

    Args:
        user_id (int): The ID of the user.
        amount (float): The amount of cash to deposit.

    Returns:
        bool: True if the deposit was successful, False otherwise.
    """
    session = db_conn.get_session()
    try:
        session.add(CashTransaction(
            cashTransactionType='deposit',
            amount=abs(Decimal(str(amount))),
            userId=user_id,
        ))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
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

    Returns:
        bool: True if the withdrawal was successful, False otherwise.
    """
    session = db_conn.get_session()
    try:
        if not db_conn.lock_user(session, user_id):
            session.rollback()
            return False

        # Validate that the user has sufficient funds to make the withdrawal,
        # re-checked under the user row lock so no other request can race it
        withdrawal = abs(Decimal(str(amount)))
        if ut.get_user_balance(user_id) < withdrawal:
            print("Insufficient funds for withdrawal.")
            session.rollback()
            return False

        session.add(CashTransaction(
            cashTransactionType='withdraw',
            amount=-withdrawal,
            userId=user_id,
        ))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error performing cash withdrawal: {e}")
        return False
