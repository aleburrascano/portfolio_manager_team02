from helpers import register_user


def test_register_returns_new_user_with_links(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'Ada', 'password': 'password1', 'firstName': 'Ada', 'lastName': 'Lovelace',
    })
    body = response.get_json()

    assert response.status_code == 201
    assert body['username'] == 'ada'
    assert '_links' in body


def test_register_rejects_missing_fields(client):
    response = client.post('/api/v1/auth/register', json={'username': 'ada', 'password': 'password1'})
    assert response.status_code == 400


def test_register_rejects_short_password(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'ada', 'password': 'short', 'firstName': 'Ada', 'lastName': 'Lovelace',
    })
    assert response.status_code == 400


def test_register_rejects_overlong_username(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'a' * 33, 'password': 'password1', 'firstName': 'Ada', 'lastName': 'Lovelace',
    })
    assert response.status_code == 400
    assert '32 characters' in response.get_json()['error']['message']


def test_register_rejects_overlong_name(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'ada', 'password': 'password1', 'firstName': 'A' * 33, 'lastName': 'Lovelace',
    })
    assert response.status_code == 400


def test_register_rejects_name_with_digits(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'ada', 'password': 'password1', 'firstName': 'Ada2', 'lastName': 'Lovelace',
    })
    assert response.status_code == 400


def test_register_rejects_username_with_spaces(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'ada lovelace', 'password': 'password1',
        'firstName': 'Ada', 'lastName': 'Lovelace',
    })
    assert response.status_code == 400


def test_register_accepts_a_hyphenated_name(client):
    response = client.post('/api/v1/auth/register', json={
        'username': 'ada', 'password': 'password1',
        'firstName': "Ada-Marie", 'lastName': "O'Lovelace",
    })
    assert response.status_code == 201


def test_update_rejects_overlong_username(client):
    user = register_user(client, username='ada')
    response = client.patch(f'/api/v1/users/{user["userId"]}', json={'username': 'a' * 33})
    assert response.status_code == 400


def test_register_rejects_duplicate_username(client):
    register_user(client, username='ada')
    response = client.post('/api/v1/auth/register', json={
        'username': 'ada', 'password': 'password1', 'firstName': 'Ada', 'lastName': 'Lovelace',
    })
    assert response.status_code == 409


def test_login_succeeds_with_correct_credentials(client):
    register_user(client, username='ada', password='password1')
    response = client.post('/api/v1/auth/login', json={'username': 'ada', 'password': 'password1'})
    assert response.status_code == 200


def test_login_rejects_wrong_password(client):
    register_user(client, username='ada', password='password1')
    response = client.post('/api/v1/auth/login', json={'username': 'ada', 'password': 'wrong'})
    assert response.status_code == 401


def test_login_rejects_missing_fields(client):
    response = client.post('/api/v1/auth/login', json={'username': 'ada'})
    assert response.status_code == 400


def test_me_reflects_the_logged_in_user(client):
    user = register_user(client, username='ada')
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 200
    assert response.get_json()['userId'] == user['userId']


def test_me_requires_a_session(client):
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 401


def test_logout_clears_the_session(client):
    register_user(client, username='ada')
    client.post('/api/v1/auth/logout')
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 401


def test_get_user_requires_authentication(client):
    response = client.get('/api/v1/users/1')
    assert response.status_code == 401


def test_get_user_rejects_accessing_another_users_data(client):
    user = register_user(client, username='ada')
    response = client.get(f'/api/v1/users/{user["userId"] + 1}')
    assert response.status_code == 403


def test_get_user_returns_own_profile(client):
    user = register_user(client, username='ada')
    response = client.get(f'/api/v1/users/{user["userId"]}')
    assert response.status_code == 200
    assert response.get_json()['username'] == 'ada'
