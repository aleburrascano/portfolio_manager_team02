from turtle import st
from typing import Tuple
from flask import Blueprint
from services.user_transactions import get_user_balance
import services.cash_transactions as ct

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route('/users/<int:user_id>/balance', methods=['GET'])
def get_wallet_balance(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's current wallet balance.

    Returns:
        dict: {'userId': int, 'balance': float}, or a 500 error if the
        database connection failed.
    """
    balance = get_user_balance(user_id)
    if balance is None:
        return {'error': 'Database connection failed'}, 500

    return {'userId': user_id, 'balance': balance}, 200

@wallet_bp.route('/users/<int:user_id>/deposit', methods=['POST'])
def deposit_cash(user_id: int, amount: float) -> Tuple[dict, int]:
    """
    Deposit cash into the user's account.
    """
    try:
        if ct.depositCash(user_id, amount):
            return {'message': 'Cash deposit successful!'}, 200
        else:
            return {'error': 'Cash deposit failed.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500

@wallet_bp.route('/users/<int:user_id>/withdraw', methods=['POST'])
def withdraw_cash(user_id: int, amount: float) -> Tuple[dict, int]:
    """
    Withdraw cash from the user's account.
    """
    try:
        if ct.withdrawCash(user_id, amount):
            return {'message': 'Cash withdrawal successful!'}, 200
        else:
            return {'error': 'Cash withdrawal failed.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500
