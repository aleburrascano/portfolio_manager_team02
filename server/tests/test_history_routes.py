import csv
import io
from decimal import Decimal

from helpers import register_user


def _deposit(client, user_id, amount=100):
    return client.post(f'/api/v1/users/{user_id}/deposit', json={'amount': amount})


def test_history_reports_the_total_before_paging(client):
    user = register_user(client)
    for _ in range(3):
        _deposit(client, user['userId'])

    body = client.get(f'/api/v1/users/{user["userId"]}/transactions?limit=2').get_json()
    assert len(body['transactions']) == 2
    assert body['total'] == 3


def test_history_pages_with_offset(client):
    user = register_user(client)
    for amount in (100, 200, 300):
        _deposit(client, user['userId'], amount)

    first = client.get(f'/api/v1/users/{user["userId"]}/transactions?limit=2').get_json()
    second = client.get(
        f'/api/v1/users/{user["userId"]}/transactions?limit=2&offset=2'
    ).get_json()

    assert len(second['transactions']) == 1
    ids = {row['transactionId'] for row in first['transactions']}
    assert ids.isdisjoint(row['transactionId'] for row in second['transactions'])


def test_history_caps_an_outsized_limit(client):
    user = register_user(client)
    _deposit(client, user['userId'])

    response = client.get(f'/api/v1/users/{user["userId"]}/transactions?limit=99999')
    assert response.status_code == 200


def test_history_reports_what_a_sale_realised(client, monkeypatch):
    import services.market_data as market_data
    monkeypatch.setattr(
        market_data, 'quote_classification',
        lambda ticker: {'exchange': 'NMS', 'quoteType': 'EQUITY'},
    )

    user = register_user(client)
    _deposit(client, user['userId'], 1000)

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('10.00'))
    client.post(f'/api/v1/users/{user["userId"]}/assets/stock/buy',
                json={'ticker': 'AAPL', 'quantity': 10})

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('15.00'))
    client.post(f'/api/v1/users/{user["userId"]}/assets/stock/sell',
                json={'ticker': 'AAPL', 'quantity': 4})

    rows = client.get(f'/api/v1/users/{user["userId"]}/transactions').get_json()['transactions']
    sale = next(row for row in rows if row['transactionType'] == 'sell')

    assert sale['realized'] == {
        'costBasis': 40.0, 'proceeds': 60.0, 'gainLoss': 20.0, 'gainLossPercent': 50.0,
    }

    assert 'realized' not in next(row for row in rows if row['transactionType'] == 'buy')
    assert 'realized' not in next(row for row in rows if row['type'] == 'cash')


def test_export_returns_csv_of_every_row(client):
    user = register_user(client)
    for _ in range(2):
        _deposit(client, user['userId'])

    response = client.get(f'/api/v1/users/{user["userId"]}/transactions/export')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'attachment' in response.headers['Content-Disposition']

    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows[0] == [
        'Date', 'Type', 'Action', 'Ticker', 'Quantity', 'Price', 'Amount',
        'Cost basis', 'Realized gain/loss',
    ]
    assert len(rows) == 3


def test_the_export_link_is_followable(client):
    user = register_user(client)
    _deposit(client, user['userId'])

    body = client.get(f'/api/v1/users/{user["userId"]}/transactions').get_json()
    response = client.get(body['_links']['export'])

    assert response.status_code == 200
    assert response.mimetype == 'text/csv'


def test_export_is_private(client):
    register_user(client)
    assert client.get('/api/v1/users/999/transactions/export').status_code == 403


def test_export_requires_authentication(client):
    assert client.get('/api/v1/users/1/transactions/export').status_code == 401


def test_export_defuses_a_formula_in_a_cell(client, monkeypatch):
    import api.routes.history as history

    monkeypatch.setattr(history, 'get_user_transactions', lambda *args, **kwargs: [{
        'transactionId': 1, 'transactionDate': '2026-01-01', 'type': 'stock',
        'transactionType': 'buy', 'ticker': '=cmd|calc', 'qty': 1, 'price': 1,
        'signedAmount': -1,
    }])

    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/transactions/export')

    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows[1][3] == "'=cmd|calc"


def test_transaction_history_requires_authentication(client):
    assert client.get('/api/v1/users/1/transactions').status_code == 401


def test_empty_history_for_new_user(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/transactions')
    assert response.status_code == 200
    assert response.get_json()['transactions'] == []


def test_history_lists_both_cash_transactions(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 100})
    client.post(f'/api/v1/users/{user["userId"]}/withdraw', json={'amount': 40})

    transactions = client.get(f'/api/v1/users/{user["userId"]}/transactions').get_json()['transactions']
    by_type = {t['transactionType']: float(t['signedAmount']) for t in transactions}

    assert len(transactions) == 2
    assert by_type == {'deposit': 100.0, 'withdraw': -40.0}


def test_history_respects_limit_and_offset(client):
    user = register_user(client)
    for amount in (10, 20, 30):
        client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': amount})

    first_page = client.get(
        f'/api/v1/users/{user["userId"]}/transactions?limit=2'
    ).get_json()['transactions']
    second_page = client.get(
        f'/api/v1/users/{user["userId"]}/transactions?limit=2&offset=2'
    ).get_json()['transactions']

    assert len(first_page) == 2
    assert len(second_page) == 1
    ids = {t['transactionId'] for t in first_page} | {t['transactionId'] for t in second_page}
    assert len(ids) == 3
