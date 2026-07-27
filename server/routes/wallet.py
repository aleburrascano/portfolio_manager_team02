from typing import Tuple
from flask import Blueprint
from services.user_transactions import get_user_balance

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
