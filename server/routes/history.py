from typing import Tuple
from flask import Blueprint, request
from services.user_transactions import get_user_transactions
from authorization import require_user
from links import transactions_links

history_bp = Blueprint('history', __name__)

MAX_PAGE_SIZE = 500

@history_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
@require_user
def get_transaction_history(user_id: int) -> Tuple[dict, int]:
    """
    Get a user's chronological transaction history (cash and asset).

    Query params:
        limit (int): Maximum rows to return, capped at MAX_PAGE_SIZE.
            Omitted returns the whole history.
        offset (int): Rows to skip, for paging.

    Returns:
        dict: {'userId': int, 'transactions': list[dict], '_links': dict}
    """
    limit = request.args.get('limit', type=int)
    if limit is not None:
        limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, request.args.get('offset', default=0, type=int))

    return {
        'userId': user_id,
        'transactions': get_user_transactions(user_id, limit, offset),
        '_links': transactions_links(user_id),
    }, 200
