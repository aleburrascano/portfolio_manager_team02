"""
The per-user watchlist: saving tickers to follow, whether or not they are
held.

Quotes are stubbed throughout - what's under test is the membership and
ownership rules, not the market feed.
"""
import pytest

import services.watchlist as watchlist
from helpers import register_user
from services.exceptions import InvalidInput


@pytest.fixture(autouse=True)
def stub_quotes(monkeypatch):
    """Every ticker quotes at $100 under a predictable name."""
    for provider in watchlist.PROVIDERS.values():
        monkeypatch.setattr(
            provider,
            'get_quote',
            lambda ticker: {
                'symbol': ticker,
                'name': f'{ticker} Inc.',
                'currentPrice': 100.0,
                'change': 1.0,
                'changePercent': 1.0,
            },
        )


def watchlist_url(user_id, asset_type='stock', ticker='AAPL'):
    return f'/api/v1/users/{user_id}/watchlist/{asset_type}/{ticker}'


def test_watchlist_starts_empty(client):
    user = register_user(client)
    response = client.get(f'/api/v1/users/{user["userId"]}/watchlist')
    assert response.status_code == 200
    assert response.get_json()['watchlist'] == []


def test_saving_then_reading_back(client):
    user = register_user(client)
    assert client.put(watchlist_url(user['userId'])).status_code == 200

    entries = client.get(f'/api/v1/users/{user["userId"]}/watchlist').get_json()['watchlist']
    assert len(entries) == 1
    assert entries[0]['symbol'] == 'AAPL'
    assert entries[0]['assetType'] == 'stock'
    assert entries[0]['currentPrice'] == 100.0


# PUT, so the button can be pressed twice without creating two entries.
def test_saving_twice_leaves_one_entry(client):
    user = register_user(client)
    client.put(watchlist_url(user['userId']))
    client.put(watchlist_url(user['userId']))

    entries = client.get(f'/api/v1/users/{user["userId"]}/watchlist').get_json()['watchlist']
    assert len(entries) == 1


def test_removing(client):
    user = register_user(client)
    client.put(watchlist_url(user['userId']))
    assert client.delete(watchlist_url(user['userId'])).status_code == 200
    assert client.get(f'/api/v1/users/{user["userId"]}/watchlist').get_json()['watchlist'] == []


def test_removing_something_never_saved_is_not_an_error(client):
    user = register_user(client)
    assert client.delete(watchlist_url(user['userId'])).status_code == 200


def test_membership_check(client):
    user = register_user(client)
    assert client.get(watchlist_url(user['userId'])).get_json()['watched'] is False
    client.put(watchlist_url(user['userId']))
    assert client.get(watchlist_url(user['userId'])).get_json()['watched'] is True


def test_tickers_are_normalised(client):
    user = register_user(client)
    client.put(watchlist_url(user['userId'], ticker='aapl'))
    assert client.get(watchlist_url(user['userId'], ticker='AAPL')).get_json()['watched'] is True


def test_newest_saved_appears_first(client):
    user = register_user(client)
    for ticker in ('AAPL', 'MSFT', 'NVDA'):
        client.put(watchlist_url(user['userId'], ticker=ticker))

    entries = client.get(f'/api/v1/users/{user["userId"]}/watchlist').get_json()['watchlist']
    assert [entry['symbol'] for entry in entries] == ['NVDA', 'MSFT', 'AAPL']


def test_any_asset_type_can_be_watched(client):
    user = register_user(client)
    client.put(watchlist_url(user['userId'], asset_type='bond', ticker='UST2Y'))
    client.put(watchlist_url(user['userId'], asset_type='crypto', ticker='BTC-USD'))

    entries = client.get(f'/api/v1/users/{user["userId"]}/watchlist').get_json()['watchlist']
    assert {entry['assetType'] for entry in entries} == {'bond', 'crypto'}


def test_unknown_asset_type_is_rejected(client):
    user = register_user(client)
    assert client.put(watchlist_url(user['userId'], asset_type='tulips')).status_code == 404


def test_the_list_is_capped(client, monkeypatch):
    monkeypatch.setattr(watchlist, 'MAX_ENTRIES', 3)
    user = register_user(client)
    for ticker in ('A', 'B', 'C'):
        assert client.put(watchlist_url(user['userId'], ticker=ticker)).status_code == 200

    overflow = client.put(watchlist_url(user['userId'], ticker='D'))
    assert overflow.status_code == 400
    assert 'full' in overflow.get_json()['error']['message']


def test_a_quote_that_fails_still_lists_the_ticker(client, monkeypatch):
    for provider in watchlist.PROVIDERS.values():
        monkeypatch.setattr(provider, 'get_quote', lambda ticker: (_ for _ in ()).throw(RuntimeError()))

    user = register_user(client)
    client.put(watchlist_url(user['userId']))

    entries = client.get(f'/api/v1/users/{user["userId"]}/watchlist').get_json()['watchlist']
    assert entries[0]['symbol'] == 'AAPL'
    assert entries[0]['currentPrice'] is None


# One user's watchlist is not another's, and must not be reachable.
def test_watchlists_are_private(client):
    alice = register_user(client, username='alice')
    client.put(watchlist_url(alice['userId']))

    assert client.get('/api/v1/users/999/watchlist').status_code == 403
    assert client.put(watchlist_url(999)).status_code == 403
    assert client.delete(watchlist_url(999)).status_code == 403


def test_watchlist_requires_authentication(client):
    assert client.get('/api/v1/users/1/watchlist').status_code == 401
    assert client.put(watchlist_url(1)).status_code == 401
    assert client.delete(watchlist_url(1)).status_code == 401


def test_saving_does_not_create_an_asset_row(client):
    """
    A watched ticker has not been transacted, so it must not appear in
    Assets - that table is what the portfolio breakdown groups by.
    """
    from db.connection import get_session
    from db.models import Asset

    user = register_user(client)
    client.put(watchlist_url(user['userId'], ticker='ZZZZ'))

    with client.application.app_context():
        assert get_session().get(Asset, 'ZZZZ') is None
