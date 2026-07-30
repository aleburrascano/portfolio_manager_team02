from typing import Tuple
from flask import Blueprint
from services.user_transactions import get_user_transactions
from authorization import require_user
from links import transactions_links

history_bp = Blueprint('history', __name__)

@history_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
@require_user
def get_transaction_history(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's chronological transaction history (cash and stock).

    Returns:
        dict: {'userId': int, 'transactions': list[dict], '_links': dict}
    """
    return {
        'userId': user_id,
        'transactions': get_user_transactions(user_id),
        '_links': transactions_links(user_id),
    }, 200
