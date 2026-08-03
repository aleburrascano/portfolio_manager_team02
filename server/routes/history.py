from typing import Tuple
from services.user_transactions import get_user_transactions
from apidocs import Blueprint
from authorization import require_user
from links import transactions_links
from schemas import TransactionsQuerySchema

history_bp = Blueprint('history', __name__, description='Transaction history')

MAX_PAGE_SIZE = 500

@history_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
@require_user
@history_bp.arguments(TransactionsQuerySchema, location='query')
def get_transaction_history(query: dict, user_id: int) -> Tuple[dict, int]:
    """
    Get a user's chronological transaction history (cash and asset).

    Returns:
        dict: {'userId': int, 'transactions': list[dict], '_links': dict}
    """
    limit = query.get('limit')
    if limit is not None:
        limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, query.get('offset') or 0)

    return {
        'userId': user_id,
        'transactions': get_user_transactions(user_id, limit, offset),
        '_links': transactions_links(user_id),
    }, 200
