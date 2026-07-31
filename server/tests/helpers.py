"""Shared test helpers that exercise the app through its real HTTP routes."""


def register_user(client, username='alice', password='hunter22', first='Alice', last='Anderson'):
    """Register + log in a user through the real HTTP routes, returning the user dict."""
    response = client.post('/api/v1/auth/register', json={
        'username': username,
        'password': password,
        'firstName': first,
        'lastName': last,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()
