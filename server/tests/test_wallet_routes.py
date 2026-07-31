from helpers import register_user


def test_balance_starts_at_zero(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/balance')
    assert response.status_code == 200
    assert response.get_json()['balance'] == 0.0


def test_deposit_increases_balance(client):
    user = register_user(client)
    deposit = client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 100})
    assert deposit.status_code == 200

    balance = client.get(f'/api/v1/users/{user["userId"]}/balance')
    assert balance.get_json()['balance'] == 100.0


def test_deposit_rejects_non_positive_amount(client):
    user = register_user(client)
    response = client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': -5})
    assert response.status_code == 400


def test_withdraw_rejects_amount_over_balance(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 50})
    response = client.post(f'/api/v1/users/{user["userId"]}/withdraw', json={'amount': 100})
    assert response.status_code == 400


def test_withdraw_decreases_balance(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 100})
    withdraw = client.post(f'/api/v1/users/{user["userId"]}/withdraw', json={'amount': 40})
    assert withdraw.status_code == 200

    balance = client.get(f'/api/v1/users/{user["userId"]}/balance')
    assert balance.get_json()['balance'] == 60.0


def test_wallet_routes_require_authentication(client):
    assert client.get('/api/v1/users/1/balance').status_code == 401
    assert client.post('/api/v1/users/1/deposit', json={'amount': 1}).status_code == 401
    assert client.post('/api/v1/users/1/withdraw', json={'amount': 1}).status_code == 401


def test_portfolio_breakdown_starts_all_zero(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/portfolio')
    assert response.status_code == 200
    assert response.get_json() == {
        'cash': 0.0, 'stock': 0.0, 'crypto': 0.0, 'bond': 0.0,
        '_links': response.get_json()['_links'],
    }


def test_portfolio_breakdown_reflects_cash_deposits(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 250})
    response = client.get(f'/api/v1/users/{user["userId"]}/portfolio')
    assert response.get_json()['cash'] == 250.0
