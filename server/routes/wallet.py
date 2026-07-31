"""
Routes for reading and updating a user's cash wallet balance.
"""
from typing import Tuple
from flask import Blueprint, request
from services.user_transactions import get_user_balance
import services.cash_transactions as ct
import services.asset_transactions as at
import services.portfolio_performance as pp
from authorization import require_user
from idempotency import idempotent
from links import balance_links, portfolio_links
from validation import parse_amount

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route('/users/<int:user_id>/balance', methods=['GET'])
@require_user
def get_wallet_balance(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's current wallet balance.

    Returns:
        dict: {'userId': int, 'balance': float, '_links': dict}
    """
    return {
        'userId': user_id,
        'balance': round(float(get_user_balance(user_id)), 2),
        '_links': balance_links(user_id),
    }, 200

@wallet_bp.route('/users/<int:user_id>/portfolio', methods=['GET'])
@require_user
def get_portfolio_breakdown(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's portfolio breakdown across cash, stocks, crypto, and bonds.

    Returns:
        dict: {'cash': float, 'stock': float, 'crypto': float, 'bond': float, '_links': dict}
    """
    return {**at.get_portfolio_values(user_id), '_links': portfolio_links(user_id)}, 200

@wallet_bp.route('/users/<int:user_id>/deposit', methods=['POST'])
@require_user
@idempotent
def deposit_cash(user_id: int) -> Tuple[dict, int]:
    """
    Deposit cash into the user's account.

    Body:
        dict: {'amount': float}

    Returns:
        dict: A success message, or a 400 error.
    """
    amount = parse_amount((request.get_json(silent=True) or {}).get('amount'))
    ct.deposit_cash(user_id, amount)
    return {'message': 'Cash deposit successful!', '_links': balance_links(user_id)}, 200

@wallet_bp.route('/users/<int:user_id>/withdraw', methods=['POST'])
@require_user
@idempotent
def withdraw_cash(user_id: int) -> Tuple[dict, int]:
    """
    Withdraw cash from the user's account.

    Body:
        dict: {'amount': float}

    Returns:
        dict: A success message, or a 400 error.
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
    amount = parse_amount((request.get_json(silent=True) or {}).get('amount'))
    ct.withdraw_cash(user_id, amount)
    return {'message': 'Cash withdrawal successful!', '_links': balance_links(user_id)}, 200
