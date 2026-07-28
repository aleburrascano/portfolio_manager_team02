"""
Routes for searching stocks and buying/selling stock for a user.
"""
from typing import Tuple
from flask import Blueprint, request
import yfinance as yf
import services.stock_transactions as st

stocks_bp = Blueprint('stocks', __name__)

# Yahoo Finance exchange codes for Nasdaq, NYSE, and NYSE American/Arca.
US_EXCHANGES = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}

def _quote_fields(fast_info) -> dict:
    """Extract price/change/day-range fields from a fast_info object."""
    last_price = fast_info.get('lastPrice')
    previous_close = fast_info.get('previousClose')
    change = last_price - previous_close if last_price is not None and previous_close else None
    return {
        'currentPrice': last_price,
        'change': change,
        'changePercent': change / previous_close * 100 if change is not None and previous_close else None,
        'dayLow': fast_info.get('dayLow'),
        'dayHigh': fast_info.get('dayHigh'),
    }

@stocks_bp.route('/stocks/search', methods=['GET'])
def search_stocks() -> Tuple[dict, int]:
    """
    Search for stocks by ticker or company name.

    Query params:
        q (str): The search query.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', 'change', 'changePercent', 'dayLow', and 'dayHigh'.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return {'error': 'Search query required'}, 400

    try:
        search = yf.Search(query, max_results=10)
        names = {}
        for quote in search.quotes:
            symbol = quote.get('symbol')
            if symbol and quote.get('exchange') in US_EXCHANGES:
                names[symbol] = quote.get('longname', quote.get('shortname', 'N/A'))

        results = []
        if names:
            tickers = yf.Tickers(' '.join(names.keys()))
            for symbol, name in names.items():
                stock = {'symbol': symbol, 'name': name}
                try:
                    stock.update(_quote_fields(tickers.tickers[symbol].fast_info))
                except Exception:
                    pass
                results.append(stock)

        return {'results': results}, 200
    except Exception as e:
        return {'error': str(e), 'results': []}, 200

@stocks_bp.route('/stocks/popular', methods=['GET'])
def get_popular_stocks() -> Tuple[dict, int]:
    """
    Get the top 10 most actively traded stocks.

    Returns:
        dict: {'results': list[dict]}, each with 'symbol', 'name',
        'currentPrice', 'volume', 'change', 'changePercent', 'dayLow',
        and 'dayHigh'.
    """
    try:
        results = yf.screen("most_actives")
        stocks = []

        for quote in results.get('quotes', [])[:10]:
            stocks.append({
                'symbol': quote['symbol'],
                'name': quote.get('shortName', 'N/A'),
                'currentPrice': quote.get('regularMarketPrice'),
                'volume': quote.get('regularMarketVolume'),
                'change': quote.get('regularMarketChange'),
                'changePercent': quote.get('regularMarketChangePercent'),
                'dayLow': quote.get('regularMarketDayLow'),
                'dayHigh': quote.get('regularMarketDayHigh'),
            })

        return {'results': stocks}, 200
    except Exception as e:
        return {'error': str(e), 'results': []}, 200

@stocks_bp.route('/stocks/<ticker>', methods=['GET'])
def get_stock_detail(ticker: str) -> Tuple[dict, int]:
    """
    Get quote details for a single stock.

    Returns:
        dict: {'symbol', 'name', 'currentPrice', 'change', 'changePercent',
        'dayLow', 'dayHigh', 'open', 'yearLow', 'yearHigh', 'volume'}, or a
        404 if the ticker isn't found.
    """
    try:
        stock = yf.Ticker(ticker)
        fast_info = stock.fast_info
        last_price = fast_info.get('lastPrice')
        if last_price is None:
            return {'error': 'Stock not found'}, 404

        previous_close = fast_info.get('previousClose')
        change = last_price - previous_close if previous_close else None

        return {
            'symbol': ticker.upper(),
            'name': stock.info.get('longName', stock.info.get('shortName', ticker.upper())),
            **_quote_fields(fast_info),
            'open': fast_info.get('open'),
            'yearLow': fast_info.get('yearLow'),
            'yearHigh': fast_info.get('yearHigh'),
            'volume': fast_info.get('lastVolume'),
        }, 200
    except Exception:
        return {'error': 'Stock not found'}, 404

@stocks_bp.route('/stocks/<ticker>/history', methods=['GET'])
def get_stock_history(ticker: str) -> Tuple[dict, int]:
    """
    Get a year of daily closing prices for a stock, for charting.

    Returns:
        dict: {'history': list[{'date': str, 'close': float}]}
    """
    try:
        stock = yf.Ticker(ticker)
        prices = stock.history(period='1y')
        history = [
            {'date': index.strftime('%Y-%m-%d'), 'close': float(row['Close'])}
            for index, row in prices.iterrows()
        ]
        return {'history': history}, 200
    except Exception as e:
        return {'error': str(e), 'history': []}, 200

@stocks_bp.route('/users/<int:user_id>/stocks/<ticker>/holdings', methods=['GET'])
def get_stock_holdings(user_id: int, ticker: str) -> Tuple[dict, int]:
    """
    Get how many shares of a stock the user currently owns.

    Returns:
        dict: {'shares': float}
    """
    return {'shares': st.get_holding_qty(user_id, ticker)}, 200

@stocks_bp.route('/users/<int:user_id>/stocks/buy', methods=['POST'])
def buy_stock(user_id: int) -> Tuple[dict, int]:
    """
    Buy stock for the user.

    Body:
        dict: {'ticker': str, 'quantity': int}

    Returns:
        dict: A success message, or a 400/500 error.
    """
    body = request.get_json(silent=True) or {}
    ticker = body.get('ticker')
    quantity = body.get('quantity')
    if not ticker or not quantity:
        return {'error': 'ticker and quantity are required'}, 400

    try:
        if st.purchase_stock(user_id, ticker, quantity):
            return {'message': 'Stock purchase successful!'}, 200
        else:
            return {'error': 'Stock purchase failed. Check your balance.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500

@stocks_bp.route('/users/<int:user_id>/stocks/sell', methods=['POST'])
def sell_stock(user_id: int) -> Tuple[dict, int]:
    """
    Sell stock for the user.

    Body:
        dict: {'ticker': str, 'quantity': int}

    Returns:
        dict: A success message, or a 400/500 error.
    """
    body = request.get_json(silent=True) or {}
    ticker = body.get('ticker')
    quantity = body.get('quantity')
    if not ticker or not quantity:
        return {'error': 'ticker and quantity are required'}, 400

    try:
        if st.sell_stock(user_id, ticker, quantity):
            return {'message': 'Stock sale successful!'}, 200
        else:
            return {'error': 'Stock sale failed. Check your holdings.'}, 400
    except Exception as e:
        return {'error': str(e)}, 500