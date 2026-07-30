"""
Routes for searching, quoting, and buying/selling assets (stocks and
crypto), dispatched by an `asset_type` URL segment onto an AssetProvider.

These handlers only speak HTTP: market data comes from
services.market_data, and a failed trade raises out of
services.asset_transactions into the shared error handler.
"""
from functools import wraps
from typing import Optional, Tuple

from flask import Blueprint, request

import services.asset_transactions as st
import services.market_data as market_data
from services.asset_providers import PROVIDERS
from authorization import require_user
from idempotency import idempotent
from errors import error_response
from links import asset_detail_links, asset_summary_links, holdings_links

assets_bp = Blueprint('assets', __name__)


def known_asset_type(view):
    """404 any route whose <asset_type> segment isn't a supported type."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if kwargs.get('asset_type') not in PROVIDERS:
            return error_response('Unknown asset type', 404)
        return view(*args, **kwargs)

    return wrapped


def _trade_request() -> Tuple[Optional[str], Optional[float]]:
    """Pull (ticker, quantity) out of a buy/sell request body."""
    body = request.get_json(silent=True) or {}
    return body.get('ticker'), body.get('quantity')


@assets_bp.route('/assets/<asset_type>/search', methods=['GET'])
@known_asset_type
def search_assets(asset_type: str) -> Tuple[dict, int]:
    """
    Search for assets by ticker or name.

    Query params:
        q (str): The search query.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', 'change', 'changePercent', 'dayLow', and 'dayHigh'.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return error_response('Search query required', 400)

    results = market_data.search_assets(query, PROVIDERS[asset_type].matches_quote)
    for asset in results:
        asset['_links'] = asset_summary_links(asset_type, asset['symbol'])
    return {'results': results}, 200


@assets_bp.route('/assets/<asset_type>/popular', methods=['GET'])
@known_asset_type
def get_popular_assets(asset_type: str) -> Tuple[dict, int]:
    """
    Get around 10 popular assets of this type.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', 'volume', 'change', 'changePercent', 'dayLow',
        and 'dayHigh'.
    """
    results = PROVIDERS[asset_type].fetch_popular()
    for asset in results:
        asset['_links'] = asset_summary_links(asset_type, asset['symbol'])
    return {'results': results}, 200


@assets_bp.route('/assets/<asset_type>/<ticker>', methods=['GET'])
@known_asset_type
def get_asset_detail(asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get quote details for a single asset.

    Returns:
        dict: {'symbol', 'name', 'currentPrice', 'change', 'changePercent',
        'dayLow', 'dayHigh', 'open', 'yearLow', 'yearHigh', 'volume'}, or a
        404 if the asset type or ticker isn't found.
    """
    quote = market_data.asset_quote(ticker)
    if quote is None:
        return error_response('Asset not found', 404)

    return {**quote, '_links': asset_detail_links(asset_type, ticker)}, 200


@assets_bp.route('/assets/<asset_type>/<ticker>/history', methods=['GET'])
@known_asset_type
def get_asset_history(asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get a year of daily closing prices for an asset, for charting.

    Returns:
        dict: {'history': list[{'date': str, 'close': float}]}
    """
    return {'history': market_data.price_history(ticker)}, 200


@assets_bp.route('/users/<int:user_id>/assets/<asset_type>/<ticker>/holdings', methods=['GET'])
@require_user
@known_asset_type
def get_asset_holdings(user_id: int, asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get how many shares/units of an asset the user currently owns.

    Returns:
        dict: {'shares': float}
    """
    return {
        'shares': st.get_holding_qty(user_id, ticker),
        '_links': holdings_links(user_id, asset_type, ticker),
    }, 200


@assets_bp.route('/users/<int:user_id>/assets/<asset_type>/buy', methods=['POST'])
@require_user
@known_asset_type
@idempotent
def buy_asset(user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    Buy an asset for the user.

    Body:
        dict: {'ticker': str, 'quantity': float}

    Returns:
        dict: A success message, or a 400/404/502 error.
    """
    ticker, quantity = _trade_request()
    if not ticker or not quantity:
        return error_response('ticker and quantity are required', 400)

    st.purchase_asset(user_id, asset_type, ticker, quantity)
    return {'message': 'Purchase successful!', '_links': holdings_links(user_id, asset_type, ticker)}, 200


@assets_bp.route('/users/<int:user_id>/assets/<asset_type>/sell', methods=['POST'])
@require_user
@known_asset_type
@idempotent
def sell_asset(user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    Sell an asset for the user.

    Body:
        dict: {'ticker': str, 'quantity': float}

    Returns:
        dict: A success message, or a 400/404/502 error.
    """
    ticker, quantity = _trade_request()
    if not ticker or not quantity:
        return error_response('ticker and quantity are required', 400)

    st.sell_asset(user_id, asset_type, ticker, quantity)
    return {'message': 'Sale successful!', '_links': holdings_links(user_id, asset_type, ticker)}, 200
