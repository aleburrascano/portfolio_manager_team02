from typing import Tuple
from flask import Blueprint, request
import yfinance as yf
import services.stock_transactions as st

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route('/stocks/search', methods=['GET'])
def search_stocks() -> Tuple[dict, int]:
    """
    Search for stocks by ticker or company name.

    Query params:
        q (str): The search query.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol' and 'name'.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return {'error': 'Search query required'}, 400

    try:
        search = yf.Search(query, max_results=10)
        results = []

        for quote in search.quotes:
            symbol = quote.get('symbol')
            if not symbol:
                continue
            results.append({
                'symbol': symbol,
                'name': quote.get('longname', quote.get('shortname', 'N/A')),
            })

        return {'results': results}, 200
    except Exception as e:
        return {'error': str(e), 'results': []}, 200

@stocks_bp.route('/stocks/popular', methods=['GET'])
def get_popular_stocks() -> Tuple[dict, int]:
    """
    Get the top 10 most actively traded stocks.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', and 'volume'.
    """
    try:
        results = yf.screen("most_actives")
        stocks = []

        for quote in results.get('quotes', [])[:10]:
            stocks.append({
                'symbol': quote['symbol'],
                'name': quote.get('shortName', 'N/A'),
                'currentPrice': quote.get('regularMarketPrice'),
                'volume': quote.get('regularMarketVolume')
            })

        return {'results': stocks}, 200
    except Exception as e:
        return {'error': str(e), 'results': []}, 200

@stocks_bp.route('/stocks/buy', methods=['POST'])
def buy_stock(user_id: int, ticker: str, quantity: int) -> Tuple[dict, int]:
    """
    Buy stock for the user.
    """
    try:
        if st.purchaseStock(user_id, ticker, quantity):
            return {'message': 'Stock purchase successful!'}, 200
        else:
            return {'error': 'Stock purchase failed. Check your balance.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500

@stocks_bp.route('/stocks/sell', methods=['POST'])
def sell_stock(user_id: int, ticker: str, quantity: int) -> Tuple[dict, int]:
    """
    Sell stock for the user.
    """
    try:
        if st.sellStock(user_id, ticker, quantity):
            return {'message': 'Stock sale successful!'}, 200
        else:
            return {'error': 'Stock sale failed. Check your holdings.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500