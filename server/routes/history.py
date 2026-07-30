from typing import Tuple
from flask import Blueprint
from services.user_transactions import get_user_transactions
from errors import error_response
from links import transactions_links

history_bp = Blueprint('history', __name__)

@history_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
def get_transaction_history(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's chronological transaction history (cash and stock).

    Returns:
        dict: {'userId': int, 'transactions': list[dict], '_links': dict},
        or a 500 error if the database connection failed.
    """
    transactions = get_user_transactions(user_id)
    if transactions is None:
        return error_response('Database connection failed', 500)

    return {
        'userId': user_id,
        'transactions': transactions,
        '_links': transactions_links(user_id),
    }, 200
