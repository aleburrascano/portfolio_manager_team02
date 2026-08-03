"""
Routes for placing, cancelling, and listing GTC limit orders on stocks.
"""
from typing import Tuple

from flask import Blueprint, request

import services.limit_orders as lo
from authorization import require_user
from errors import error_response
from idempotency import idempotent
from links import limit_order_links, limit_orders_links
from routes.assets import known_asset_type
from services.exceptions import InvalidInput
from validation import parse_limit_price, parse_quantity, parse_side

limit_orders_bp = Blueprint('limit_orders', __name__)


def _serialize(order) -> dict:
    return {
        'limitOrderId': order.limitOrderId,
        'ticker': order.ticker,
        'side': order.side,
        'quantity': float(order.quantity),
        'limitPrice': float(order.limitPrice),
        'status': order.status,
        'createdAt': order.createdAt.isoformat(),
        'resolvedAt': order.resolvedAt.isoformat() if order.resolvedAt else None,
        'assetTransactionId': order.assetTransactionId,
        '_links': limit_order_links(order.userId, order.limitOrderId),
    }


def _place_request():
    """
    Pull a validated (ticker, side, quantity, limitPrice) out of a place
    request body.

    Raises:
        InvalidInput: if any field is missing or malformed.
    """
    body = request.get_json(silent=True) or {}
    ticker = body.get('ticker')
    if not isinstance(ticker, str) or not ticker.strip():
        raise InvalidInput('ticker is required.')
    return (
        ticker.strip(),
        parse_side(body.get('side')),
        parse_quantity(body.get('quantity')),
        parse_limit_price(body.get('limitPrice')),
    )


@limit_orders_bp.route('/users/<int:user_id>/assets/<asset_type>/limit-orders', methods=['POST'])
@require_user
@known_asset_type
@idempotent
def place_limit_order(user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    Place a GTC limit order.

    Body:
        dict: {'ticker': str, 'side': 'buy'|'sell', 'quantity': float, 'limitPrice': float}

    Returns:
        dict: {'order': dict}, or a 400/404/502 error.
    """
    ticker, side, quantity, limit_price = _place_request()
    order = lo.place_limit_order(user_id, asset_type, ticker, side, quantity, limit_price)
    return {'order': _serialize(order)}, 201


@limit_orders_bp.route('/users/<int:user_id>/assets/<asset_type>/limit-orders', methods=['GET'])
@require_user
@known_asset_type
def list_limit_orders(user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    List this user's limit orders.

    Query params:
        status ('pending'|'filled'|'cancelled'): filter, omitted returns all.

    Returns:
        dict: {'orders': list[dict], '_links': dict}
    """
    status = request.args.get('status')
    if status not in (None, 'pending', 'filled', 'cancelled'):
        return error_response('invalid status', 400)

    orders = lo.list_limit_orders(user_id, status)
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
