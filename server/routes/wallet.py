"""
Routes for reading and updating a user's cash wallet balance.
"""
from typing import Tuple
from flask import Blueprint, request
from services.user_transactions import get_user_balance
import services.cash_transactions as ct
import services.asset_transactions as at
from errors import error_response
from links import balance_links, portfolio_links

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route('/users/<int:user_id>/balance', methods=['GET'])
def get_wallet_balance(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's current wallet balance.

    Returns:
        dict: {'userId': int, 'balance': float, '_links': dict}, or a 500
        error if the database connection failed.
    """
    balance = get_user_balance(user_id)
    if balance is None:
        return error_response('Database connection failed', 500)

    return {
        'userId': user_id,
        'balance': round(float(balance), 2),
        '_links': balance_links(user_id),
    }, 200

@wallet_bp.route('/users/<int:user_id>/portfolio', methods=['GET'])
def get_portfolio_breakdown(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's portfolio breakdown across cash, stocks, crypto, and bonds.

    Returns:
        dict: {'cash': float, 'stock': float, 'crypto': float, 'bond': float, '_links': dict}
    """
    try:
        data = at.get_portfolio_values(user_id)
        return {**data, '_links': portfolio_links(user_id)}, 200
    except Exception as e:
        return error_response(str(e), 500)

@wallet_bp.route('/users/<int:user_id>/deposit', methods=['POST'])
def deposit_cash(user_id: int) -> Tuple[dict, int]:
    """
    Deposit cash into the user's account.

    Body:
        dict: {'amount': float}

    Returns:
        dict: A success message, or a 400/500 error.
    """
    amount = (request.get_json(silent=True) or {}).get('amount')
    if amount is None:
        return error_response('amount is required', 400)

    try:
        if ct.deposit_cash(user_id, amount):
            return {'message': 'Cash deposit successful!', '_links': balance_links(user_id)}, 200
        else:
            return error_response('Cash deposit failed.', 400)
    except Exception as e:
        return error_response(str(e), 500)

@wallet_bp.route('/users/<int:user_id>/withdraw', methods=['POST'])
def withdraw_cash(user_id: int) -> Tuple[dict, int]:
    """
    Withdraw cash from the user's account.

    Body:
        dict: {'amount': float}

    Returns:
        dict: A success message, or a 400/500 error.
    """
    amount = (request.get_json(silent=True) or {}).get('amount')
    if amount is None:
        return error_response('amount is required', 400)

    try:
        if ct.withdraw_cash(user_id, amount):
            return {'message': 'Cash withdrawal successful!', '_links': balance_links(user_id)}, 200
        else:
            return error_response('Cash withdrawal failed.', 400)
    except Exception as e:
        return error_response(str(e), 500)
