from flask import Blueprint, request
import yfinance as yf

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route('/stocks/search', methods=['GET'])
def search_stocks():
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
def get_popular_stocks():
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
