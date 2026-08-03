"""
Routes for placing, cancelling, and listing GTC conditional orders.
"""
from typing import Tuple

import services.limit_orders as lo
from apidocs import IDEMPOTENCY_KEY, Blueprint
from authorization import require_user
from idempotency import idempotent
from links import limit_order_links, limit_orders_links
from routes.assets import known_asset_type
from routes.history import MAX_PAGE_SIZE
from schemas import LimitOrderQuerySchema, LimitOrderSchema

limit_orders_bp = Blueprint('limit_orders', __name__, description='GTC conditional orders')


def _serialize(order) -> dict:
    return {
        'limitOrderId': order.limitOrderId,
        'ticker': order.ticker,
        'side': order.side,
        'orderType': order.orderType,
        'quantity': float(order.quantity),
        'limitPrice': float(order.limitPrice),
        'status': order.status,
        'createdAt': order.createdAt.isoformat(),
        'resolvedAt': order.resolvedAt.isoformat() if order.resolvedAt else None,
        'assetTransactionId': order.assetTransactionId,
        '_links': limit_order_links(order.userId, order.limitOrderId),
    }


@limit_orders_bp.route('/users/<int:user_id>/assets/<asset_type>/limit-orders', methods=['POST'])
@require_user
@known_asset_type
@idempotent
@limit_orders_bp.doc(parameters=[IDEMPOTENCY_KEY])
@limit_orders_bp.arguments(LimitOrderSchema)
def place_limit_order(body: dict, user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    Place a GTC conditional order, either a limit or a stop.

    Returns:
        dict: {'order': dict}, or a 400/404/502 error.
    """
    order = lo.place_limit_order(
        user_id, asset_type,
        body['ticker'], body['side'], body['quantity'], body['limitPrice'],
        body['orderType'],
    )
    return {'order': _serialize(order)}, 201


@limit_orders_bp.route('/users/<int:user_id>/assets/<asset_type>/limit-orders', methods=['GET'])
@require_user
@known_asset_type
@limit_orders_bp.arguments(LimitOrderQuerySchema, location='query')
def list_limit_orders(query: dict, user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    List this user's conditional orders for this asset type, newest first.

    Returns:
        dict: {'orders': list[dict], '_links': dict}
    """
    limit = query.get('limit')
    if limit is not None:
        limit = max(1, min(limit, MAX_PAGE_SIZE))
    orders = lo.list_limit_orders(user_id, asset_type, query.get('status'), limit)
    return {
        'orders': [_serialize(order) for order in orders],
        '_links': limit_orders_links(user_id, asset_type),
    }, 200


@limit_orders_bp.route('/users/<int:user_id>/limit-orders/<int:limit_order_id>', methods=['DELETE'])
@require_user
def cancel_limit_order(user_id: int, limit_order_id: int) -> Tuple[dict, int]:
    """
    Cancel a pending limit order.

    Returns:
        dict: {'status': 'cancelled'}, or a 400/404 error.
    """
    lo.cancel_limit_order(user_id, limit_order_id)
    return {'status': 'cancelled'}, 200
