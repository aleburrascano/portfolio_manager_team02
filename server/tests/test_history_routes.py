from helpers import register_user


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
