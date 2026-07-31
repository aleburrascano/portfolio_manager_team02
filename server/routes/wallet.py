"""
Routes for reading and updating a user's cash wallet balance.
"""
from typing import Tuple
from flask import Blueprint, request
from services.user_transactions import get_user_balance
import services.cash_transactions as ct
import services.asset_transactions as at
import services.portfolio_performance as pp

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

    return {'userId': user_id, 'balance': round(float(balance), 2)}, 200

@wallet_bp.route('/users/<int:user_id>/portfolio', methods=['GET'])
def get_portfolio_breakdown(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's portfolio breakdown across cash, stocks, and crypto.

    Returns:
        dict: {'cash': float, 'stock': float, 'crypto': float}
    """
    try:
        data = at.get_portfolio_values(user_id)
        return data, 200
    except Exception as e:
        return {'error': str(e)}, 500

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
        return {'error': 'amount is required'}, 400

    try:
        if ct.deposit_cash(user_id, amount):
            return {'message': 'Cash deposit successful!'}, 200
        else:
            return {'error': 'Cash deposit failed.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500

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
        return {'error': 'amount is required'}, 400

    try:
        if ct.withdraw_cash(user_id, amount):
            return {'message': 'Cash withdrawal successful!'}, 200
        else:
            return {'error': 'Cash withdrawal failed.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500

@wallet_bp.route('/users/<int:user_id>/portfolio/performance', methods=['GET']) 
def get_portfolio_performance(user_id: int) -> Tuple[dict, int]: 
    """ Get a user's portfolio performance over time.
    Returns: list[dict]: [ { "date": "2026-01-01", "portfolioValue": 10235.18 }, ... ] """ 
    try: 
        data = pp.get_portfolio_performance(user_id) 
        return data, 200 
    except Exception as e: 
        return {'error': str(e)}, 500 