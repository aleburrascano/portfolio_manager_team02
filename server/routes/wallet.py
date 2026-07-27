from flask import Blueprint
from transactions import get_user_balance

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route('/users/<int:user_id>/balance', methods=['GET'])
def get_wallet_balance(user_id):
    balance = get_user_balance(user_id)
    if balance is None:
        return {'error': 'Database connection failed'}, 500

    return {'userId': user_id, 'balance': balance}, 200
