"""
Routes for searching, quoting, and buying/selling assets (stocks, crypto,
and bonds), dispatched by an `asset_type` URL segment onto an AssetProvider.

These handlers only speak HTTP. Everything type-specific is behind the
provider, so nothing here branches on what kind of asset it's handling, and
a failed trade raises out of services.asset_transactions into the shared
error handler.
"""
from decimal import Decimal
from functools import wraps
from typing import Tuple

from flask import Blueprint, request

import services.asset_transactions as st
import services.watchlist as watchlist
from services.asset_providers import PROVIDERS
from services.exceptions import InvalidInput
from authorization import require_user
from idempotency import idempotent
from errors import error_response
from links import asset_detail_links, asset_summary_links, holdings_links, watchlist_links
from validation import parse_quantity

assets_bp = Blueprint('assets', __name__)


def known_asset_type(view):
    """404 any route whose <asset_type> segment isn't a supported type."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if kwargs.get('asset_type') not in PROVIDERS:
            return error_response('Unknown asset type', 404)
        return view(*args, **kwargs)

    return wrapped


def _trade_request() -> Tuple[str, Decimal]:
    """
    Pull a validated (ticker, quantity) out of a buy/sell request body.

    Raises:
        InvalidInput: if either field is missing or malformed.
    """
    body = request.get_json(silent=True) or {}
    ticker = body.get('ticker')
    if not isinstance(ticker, str) or not ticker.strip():
        raise InvalidInput('ticker is required.')
    return ticker.strip(), parse_quantity(body.get('quantity'))


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

    results = PROVIDERS[asset_type].search(query)
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
        404 if the asset type or ticker isn't found. Fields that don't apply
        to an asset type - a bond has no volume or intraday range - are null.
    """
    quote = PROVIDERS[asset_type].get_quote(ticker)
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
    return {'history': PROVIDERS[asset_type].get_history(ticker)}, 200


@assets_bp.route('/assets/<asset_type>/<ticker>/ratings', methods=['GET'])
@known_asset_type
def get_asset_ratings(asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get analyst coverage for an asset: the consensus call, the price
    targets, and how the analysts split.

    Its own endpoint rather than part of the detail response, because it is
    a second upstream lookup and the price shouldn't wait behind it.

    Returns:
        dict: {'ratings': dict | null}. Null means nobody covers this
        ticker - normal for bonds, crypto, and smaller listings.
    """
    return {'ratings': PROVIDERS[asset_type].get_ratings(ticker)}, 200


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


@assets_bp.route('/users/<int:user_id>/watchlist', methods=['GET'])
@require_user
def get_watchlist(user_id: int) -> Tuple[dict, int]:
    """
    Get the tickers this user has saved to follow, newest first, quoted.

    Returns:
        dict: {'watchlist': list[dict], '_links': dict}
    """
    return {
        'watchlist': watchlist.list_entries(user_id),
        '_links': watchlist_links(user_id),
    }, 200


@assets_bp.route('/users/<int:user_id>/watchlist/<asset_type>/<ticker>', methods=['GET'])
@require_user
@known_asset_type
def is_watched(user_id: int, asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Whether this ticker is on the user's watchlist.

    A primary-key lookup, so the asset detail page can set its save button
    without pulling and quoting the whole list to answer a boolean.

    Returns:
        dict: {'watched': bool}
    """
    return {'watched': watchlist.is_watched(user_id, ticker)}, 200


@assets_bp.route('/users/<int:user_id>/watchlist/<asset_type>/<ticker>', methods=['PUT'])
@require_user
@known_asset_type
def add_to_watchlist(user_id: int, asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Save a ticker to the watchlist.

    PUT rather than POST because saving is idempotent - pressing the button
    twice leaves one entry, not two.

    Returns:
        dict: {'watched': true}, or a 400 if the list is full.
    """
    watchlist.add(user_id, asset_type, ticker)
    return {'watched': True, '_links': watchlist_links(user_id)}, 200


@assets_bp.route('/users/<int:user_id>/watchlist/<asset_type>/<ticker>', methods=['DELETE'])
@require_user
@known_asset_type
def remove_from_watchlist(user_id: int, asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Drop a ticker from the watchlist.

    Returns:
        dict: {'watched': false}
    """
    watchlist.remove(user_id, ticker)
    return {'watched': False, '_links': watchlist_links(user_id)}, 200


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
    st.sell_asset(user_id, asset_type, ticker, quantity)
    return {'message': 'Sale successful!', '_links': holdings_links(user_id, asset_type, ticker)}, 200
