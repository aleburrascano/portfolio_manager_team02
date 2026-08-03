from helpers import register_user


def _deposit(client, user_id, amount, key=None):
    headers = {'Idempotency-Key': key} if key else {}
    return client.post(f'/api/v1/users/{user_id}/deposit', json={'amount': amount}, headers=headers)


def test_repeated_key_replays_the_first_response_without_repeating_the_effect(client):
    user = register_user(client)

    first = _deposit(client, user['userId'], 100, key='dep-1')
    second = _deposit(client, user['userId'], 100, key='dep-1')

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == second.get_json()

    balance = client.get(f'/api/v1/users/{user["userId"]}/balance').get_json()
    assert balance['balance'] == 100.0


def test_same_key_with_different_body_is_rejected(client):
    user = register_user(client)

    _deposit(client, user['userId'], 100, key='dep-2')
    conflict = _deposit(client, user['userId'], 200, key='dep-2')

    assert conflict.status_code == 409


def test_failed_request_releases_the_key_for_retry(client):
    user = register_user(client)

    failed = client.post(
        f'/api/v1/users/{user["userId"]}/withdraw',
        json={'amount': 50},
        headers={'Idempotency-Key': 'wd-1'},
    )
    assert failed.status_code == 400

    _deposit(client, user['userId'], 50, key='dep-3')
    retried = client.post(
        f'/api/v1/users/{user["userId"]}/withdraw',
        json={'amount': 50},
        headers={'Idempotency-Key': 'wd-1'},
    )
    assert retried.status_code == 200


def test_key_over_max_length_is_rejected(client):
    user = register_user(client)
    response = _deposit(client, user['userId'], 100, key='x' * 65)
    assert response.status_code == 400


def test_omitting_the_header_behaves_like_before(client):
    user = register_user(client)
    first = _deposit(client, user['userId'], 100)
    second = _deposit(client, user['userId'], 100)

    assert first.status_code == 200
    assert second.status_code == 200

    balance = client.get(f'/api/v1/users/{user["userId"]}/balance').get_json()
    assert balance['balance'] == 200.0
