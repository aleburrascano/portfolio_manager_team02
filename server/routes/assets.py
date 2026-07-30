"""
Routes for searching, quoting, and buying/selling assets (stocks and
crypto), dispatched by an `asset_type` URL segment onto an AssetProvider.
"""
from typing import Tuple
from flask import Blueprint, request
import yfinance as yf
import services.asset_transactions as st
from routes.asset_providers import PROVIDERS, _quote_fields
from errors import error_body, error_response

assets_bp = Blueprint('assets', __name__)

@assets_bp.route('/assets/<asset_type>/search', methods=['GET'])
def search_assets(asset_type: str) -> Tuple[dict, int]:
    """
    Search for assets by ticker or name.

    Query params:
        q (str): The search query.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', 'change', 'changePercent', 'dayLow', and 'dayHigh'.
    """
    provider = PROVIDERS.get(asset_type)
    if provider is None:
        return error_response('Unknown asset type', 404)

    query = request.args.get('q', '').strip()
    if not query:
        return error_response('Search query required', 400)

    try:
        search = yf.Search(query, max_results=10)
        names = {}
        for quote in search.quotes:
            symbol = quote.get('symbol')
            if symbol and provider.matches_quote(quote):
                names[symbol] = quote.get('longname', quote.get('shortname', 'N/A'))

        results = []
        if names:
            tickers = yf.Tickers(' '.join(names.keys()))
            for symbol, name in names.items():
                asset = {'symbol': symbol, 'name': name}
                try:
                    asset.update(_quote_fields(tickers.tickers[symbol].fast_info))
                except Exception:
                    pass
                results.append(asset)

        return {'results': results}, 200
    except Exception as e:
        return {**error_body(str(e)), 'results': []}, 200

@assets_bp.route('/assets/<asset_type>/popular', methods=['GET'])
def get_popular_assets(asset_type: str) -> Tuple[dict, int]:
    """
    Get around 10 popular assets of this type.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', 'volume', 'change', 'changePercent', 'dayLow',
        and 'dayHigh'.
    """
    provider = PROVIDERS.get(asset_type)
    if provider is None:
        return error_response('Unknown asset type', 404)

    try:
        return {'results': provider.fetch_popular()}, 200
    except Exception as e:
        return {**error_body(str(e)), 'results': []}, 200

@assets_bp.route('/assets/<asset_type>/<ticker>', methods=['GET'])
def get_asset_detail(asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get quote details for a single asset.

    Returns:
        dict: {'symbol', 'name', 'currentPrice', 'change', 'changePercent',
        'dayLow', 'dayHigh', 'open', 'yearLow', 'yearHigh', 'volume'}, or a
        404 if the asset type or ticker isn't found.
    """
    if asset_type not in PROVIDERS:
        return error_response('Unknown asset type', 404)

    try:
        asset = yf.Ticker(ticker)
        fast_info = asset.fast_info
        last_price = fast_info.get('lastPrice')
        if last_price is None:
            return error_response('Asset not found', 404)

        previous_close = fast_info.get('previousClose')
        change = last_price - previous_close if previous_close else None

        return {
            'symbol': ticker.upper(),
            'name': asset.info.get('longName', asset.info.get('shortName', ticker.upper())),
            **_quote_fields(fast_info),
            'open': fast_info.get('open'),
            'yearLow': fast_info.get('yearLow'),
            'yearHigh': fast_info.get('yearHigh'),
            'volume': fast_info.get('lastVolume'),
        }, 200
    except Exception:
        return error_response('Asset not found', 404)

@assets_bp.route('/assets/<asset_type>/<ticker>/history', methods=['GET'])
def get_asset_history(asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get a year of daily closing prices for an asset, for charting.

    Returns:
        dict: {'history': list[{'date': str, 'close': float}]}
    """
    if asset_type not in PROVIDERS:
        return error_response('Unknown asset type', 404)

    try:
        asset = yf.Ticker(ticker)
        prices = asset.history(period='1y')
        history = [
            {'date': index.strftime('%Y-%m-%d'), 'close': float(row['Close'])}
            for index, row in prices.iterrows()
        ]
        return {'history': history}, 200
    except Exception as e:
        return {**error_body(str(e)), 'history': []}, 200

@assets_bp.route('/users/<int:user_id>/assets/<asset_type>/<ticker>/holdings', methods=['GET'])
def get_asset_holdings(user_id: int, asset_type: str, ticker: str) -> Tuple[dict, int]:
    """
    Get how many shares/units of an asset the user currently owns.

    Returns:
        dict: {'shares': float}
    """
    if asset_type not in PROVIDERS:
        return error_response('Unknown asset type', 404)

    return {'shares': st.get_holding_qty(user_id, ticker)}, 200

@assets_bp.route('/users/<int:user_id>/assets/<asset_type>/buy', methods=['POST'])
def buy_asset(user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    Buy an asset for the user.

    Body:
        dict: {'ticker': str, 'quantity': float}

    Returns:
        dict: A success message, or a 400/404/500 error.
    """
    if asset_type not in PROVIDERS:
        return error_response('Unknown asset type', 404)

    body = request.get_json(silent=True) or {}
    ticker = body.get('ticker')
    quantity = body.get('quantity')
    if not ticker or not quantity:
        return error_response('ticker and quantity are required', 400)

    try:
        if st.purchase_asset(user_id, asset_type, ticker, quantity):
            return {'message': 'Purchase successful!'}, 200
        else:
            return error_response('Purchase failed. Check your balance.', 400)
    except Exception as e:
        return error_response(str(e), 500)

@assets_bp.route('/users/<int:user_id>/assets/<asset_type>/sell', methods=['POST'])
def sell_asset(user_id: int, asset_type: str) -> Tuple[dict, int]:
    """
    Sell an asset for the user.

    Body:
        dict: {'ticker': str, 'quantity': float}

    Returns:
        dict: A success message, or a 400/404/500 error.
    """
    if asset_type not in PROVIDERS:
        return error_response('Unknown asset type', 404)

    body = request.get_json(silent=True) or {}
    ticker = body.get('ticker')
    quantity = body.get('quantity')
    if not ticker or not quantity:
        return error_response('ticker and quantity are required', 400)

    try:
        if st.sell_asset(user_id, asset_type, ticker, quantity):
            return {'message': 'Sale successful!'}, 200
        else:
            return error_response('Sale failed. Check your holdings.', 400)
    except Exception as e:
        return error_response(str(e), 500)
