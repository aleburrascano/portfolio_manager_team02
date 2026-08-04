"""
The portfolio performance and holdings endpoints.

These went in through a merge that dropped @require_user from the
performance route, so the authorization checks here are regression tests as
much as coverage: issue #56 made session auth a rule for every user-scoped
route, and a new one must not quietly opt out of it.
"""
import services.holdings as holdings_service
import services.portfolio_performance as perf
from helpers import register_user


def test_performance_requires_authentication(client):
    assert client.get('/api/v1/users/1/portfolio/performance').status_code == 401


def test_holdings_requires_authentication(client):
    assert client.get('/api/v1/users/1/portfolio/holdings').status_code == 401


def test_performance_is_scoped_to_the_signed_in_user(client):
    register_user(client, username='alice')
    assert client.get('/api/v1/users/999/portfolio/performance').status_code == 403


def test_holdings_are_scoped_to_the_signed_in_user(client):
    register_user(client, username='alice')
    assert client.get('/api/v1/users/999/portfolio/holdings').status_code == 403


def test_performance_of_a_new_account_is_empty_not_an_error(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/portfolio/performance')

    assert response.status_code == 200
    body = response.get_json()
    assert body['series'] == []
    assert body['summary']['gainLoss'] == 0.0
    assert 'holdings' in body['_links']


def test_holdings_of_a_new_account_are_empty_not_an_error(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/portfolio/holdings')

    assert response.status_code == 200
    body = response.get_json()
    assert body['holdings'] == []
    assert body['totals']['positions'] == 0


def test_performance_reflects_a_deposit(client, monkeypatch):
    for provider in perf.PROVIDERS.values():
        monkeypatch.setattr(provider, 'get_history', lambda ticker, days=365: [])

    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 250})

    body = client.get(f'/api/v1/users/{user["userId"]}/portfolio/performance').get_json()
    assert body['series'][-1]['portfolioValue'] == 250.0
    assert body['summary']['netDeposits'] == 250.0


def test_days_window_is_validated(client):
    user = register_user(client)
    assert client.get(
        f'/api/v1/users/{user["userId"]}/portfolio/performance?days=0'
    ).status_code == 400
    assert client.get(
        f'/api/v1/users/{user["userId"]}/portfolio/performance?days=abc'
    ).status_code == 400
    assert client.get(
        f'/api/v1/users/{user["userId"]}/portfolio/performance?days=99999'
    ).status_code == 400


def test_unknown_query_params_are_ignored(client, monkeypatch):
    monkeypatch.setattr(holdings_service, 'get_user_asset_transactions', lambda user_id: [])
    user = register_user(client)

    response = client.get(
        f'/api/v1/users/{user["userId"]}/portfolio/holdings?sort=; DROP TABLE Assets'
    )
    assert response.status_code == 200
    assert response.get_json()['holdings'] == []
