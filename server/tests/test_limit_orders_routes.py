from decimal import Decimal

import pytest

import services.market_data as market_data
from helpers import register_user


@pytest.fixture(autouse=True)
def stub_market_data(monkeypatch):
    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('10.00'))
    monkeypatch.setattr(market_data, 'valuation_price', lambda ticker: 10.00)
    monkeypatch.setattr(
        market_data, 'quote_classification',
        lambda ticker: {'exchange': 'NMS', 'quoteType': 'EQUITY'},
    )


def _place(client, user_id, ticker='AAPL', side='buy', quantity=5, limit_price=8.00, key=None):
    headers = {'Idempotency-Key': key} if key else {}
    return client.post(
        f'/api/v1/users/{user_id}/assets/stock/limit-orders',
        json={'ticker': ticker, 'side': side, 'quantity': quantity, 'limitPrice': limit_price},
        headers=headers,
    )


def test_place_limit_order_returns_201_with_links(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})

    response = _place(client, user['userId'])
    assert response.status_code == 201
    body = response.get_json()
    assert body['order']['status'] == 'pending'
    assert 'cancel' in body['order']['_links']


def test_place_limit_order_unknown_asset_type_is_404(client):
    user = register_user(client)
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/nope/limit-orders',
        json={'ticker': 'AAPL', 'side': 'buy', 'quantity': 5, 'limitPrice': 8},
    )
    assert response.status_code == 404


def test_place_limit_order_non_stock_asset_type_is_400(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/crypto/limit-orders',
        json={'ticker': 'BTC', 'side': 'buy', 'quantity': 5, 'limitPrice': 8},
    )
    assert response.status_code == 400


def test_place_limit_order_rejects_missing_side(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders',
        json={'ticker': 'AAPL', 'quantity': 5, 'limitPrice': 8},
    )
    assert response.status_code == 400


def test_place_limit_order_rejects_bad_quantity(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    response = _place(client, user['userId'], quantity=-1)
    assert response.status_code == 400


def test_place_limit_order_rejects_bad_limit_price(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    response = _place(client, user['userId'], limit_price=0)
    assert response.status_code == 400


def test_place_limit_order_respects_idempotency_key(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})

    first = _place(client, user['userId'], key='order-1')
    second = _place(client, user['userId'], key='order-1')
    assert first.status_code == 201
    # A replay always answers 200 (idempotency.py's _replay), even though
    # the original request that did the work was a 201 - only the stored
    # body is guaranteed to match.
    assert second.status_code == 200
    assert first.get_json() == second.get_json()

    orders = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders').get_json()
    assert len(orders['orders']) == 1


def test_list_limit_orders_filters_by_status(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    placed = _place(client, user['userId']).get_json()['order']

    client.delete(f'/api/v1/users/{user["userId"]}/limit-orders/{placed["limitOrderId"]}')

    pending = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders?status=pending')
    assert pending.get_json()['orders'] == []

    cancelled = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders?status=cancelled')
    assert len(cancelled.get_json()['orders']) == 1


def test_list_limit_orders_is_scoped_to_the_asset_type_in_the_route(client, monkeypatch):
    import services.market_data as market_data

    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    _place(client, user['userId'])

    monkeypatch.setattr(
        market_data, 'quote_classification',
        lambda ticker: {'exchange': 'CCC', 'quoteType': 'CRYPTOCURRENCY'},
    )
    client.post(
        f'/api/v1/users/{user["userId"]}/assets/crypto/limit-orders',
        json={'ticker': 'BTC-USD', 'side': 'buy', 'quantity': 1, 'limitPrice': 8},
    )

    stocks = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders').get_json()
    crypto = client.get(f'/api/v1/users/{user["userId"]}/assets/crypto/limit-orders').get_json()

    assert [o['ticker'] for o in stocks['orders']] == ['AAPL']
    assert [o['ticker'] for o in crypto['orders']] == ['BTC-USD']


def test_list_limit_orders_honours_a_limit(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    for _ in range(3):
        _place(client, user['userId'])

    response = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders?limit=2')
    assert len(response.get_json()['orders']) == 2


def test_list_limit_orders_serializes_the_order_type(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    order = _place(client, user['userId']).get_json()['order']

    assert order['orderType'] == 'limit'
    # The fields an order history needs, which the client had typed all
    # along and no route had ever been asked for.
    assert order['resolvedAt'] is None
    assert order['assetTransactionId'] is None


# The client cancels by following this link rather than building the URL,
# so it is part of the contract: present, and actually followable.
def test_the_cancel_link_is_followable(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    order = _place(client, user['userId']).get_json()['order']

    response = client.delete(order['_links']['cancel'])

    assert response.status_code == 200
    assert response.get_json() == {'status': 'cancelled'}


def test_list_limit_orders_rejects_invalid_status(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/limit-orders?status=nope')
    assert response.status_code == 400


def test_cancel_limit_order_then_double_cancel_is_400(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})
    placed = _place(client, user['userId']).get_json()['order']

    first = client.delete(f'/api/v1/users/{user["userId"]}/limit-orders/{placed["limitOrderId"]}')
    assert first.status_code == 200
    assert first.get_json() == {'status': 'cancelled'}

    second = client.delete(f'/api/v1/users/{user["userId"]}/limit-orders/{placed["limitOrderId"]}')
    assert second.status_code == 400


def test_cancel_limit_order_for_another_user_is_404(client):
    # The URL is scoped to the caller's own userId (require_user passes),
    # but the order itself belongs to someone else - the service reports
    # that as "no such order" (404) rather than leaking that it exists
    # under a 403.
    owner = register_user(client, username='owner')
    client.post(f'/api/v1/users/{owner["userId"]}/deposit', json={'amount': 1000})
    placed = _place(client, owner['userId']).get_json()['order']

    intruder = register_user(client, username='intruder')
    response = client.delete(f'/api/v1/users/{intruder["userId"]}/limit-orders/{placed["limitOrderId"]}')
    assert response.status_code == 404


def test_cancel_unknown_limit_order_is_404(client):
    user = register_user(client)
    response = client.delete(f'/api/v1/users/{user["userId"]}/limit-orders/999')
    assert response.status_code == 404


def test_limit_order_routes_require_authentication(client):
    assert client.post(
        '/api/v1/users/1/assets/stock/limit-orders',
        json={'ticker': 'AAPL', 'side': 'buy', 'quantity': 5, 'limitPrice': 8},
    ).status_code == 401
    assert client.get('/api/v1/users/1/assets/stock/limit-orders').status_code == 401
    assert client.delete('/api/v1/users/1/limit-orders/1').status_code == 401
