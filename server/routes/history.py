from flask import Blueprint
from transactions import get_user_transactions

history_bp = Blueprint('history', __name__)

@history_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
def get_transaction_history(user_id):
    transactions = get_user_transactions(user_id)
    if transactions is None:
        return {'error': 'Database connection failed'}, 500

    return {'userId': user_id, 'transactions': transactions}, 200
