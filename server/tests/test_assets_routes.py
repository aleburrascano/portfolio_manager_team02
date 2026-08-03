from datetime import date, timedelta
from decimal import Decimal

import pytest

import services.market_data as market_data
from services.asset_providers import PROVIDERS
from db.connection import get_session
from db.models import Asset, Bond
from helpers import register_user


@pytest.fixture(autouse=True)
def stub_market_data(monkeypatch):
    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('10.00'))
    monkeypatch.setattr(market_data, 'valuation_price', lambda ticker: 10.00)
    monkeypatch.setattr(
        market_data, 'quote_classification',
        lambda ticker: {'exchange': 'NMS', 'quoteType': 'EQUITY'},
    )
    monkeypatch.setattr(
        market_data, 'search_assets',
        lambda query, matches: [{'symbol': 'AAPL', 'name': 'Apple Inc.', 'currentPrice': 10.0}],
    )


def _add_bond(app, ticker='TBOND'):
    with app.app_context():
        session = get_session()
        session.add(Asset(ticker=ticker, assetType='bond'))
        session.add(Bond(
            ticker=ticker, name='Test Bond', faceValue=Decimal('1000'),
            couponRate=Decimal('0.05'), marketYield=Decimal('0.05'),
            couponFrequency='semiannual',
            issueDate=date.today() - timedelta(days=30),
            maturityDate=date.today() + timedelta(days=365),
        ))
        session.commit()


def test_unknown_asset_type_is_404(client):
    assert client.get('/api/v1/assets/nope/popular').status_code == 404


def test_asset_types_lists_every_registered_provider(client):
    body = client.get('/api/v1/assets/types').get_json()
    by_type = {row['assetType']: row for row in body['assetTypes']}

    assert set(by_type) == set(PROVIDERS)
    assert by_type['stock'] == {
        'assetType': 'stock', 'label': 'Stocks', 'streams': True, 'supportsLimitOrders': True,
    }
    # A bond is priced from its own terms on a schedule, so it neither
    # streams nor takes a conditional order.
    assert by_type['bond']['streams'] is False
    assert by_type['bond']['supportsLimitOrders'] is False


def test_asset_types_is_public(client):
    assert client.get('/api/v1/assets/types').status_code == 200


def test_search_requires_a_query(client):
    assert client.get('/api/v1/assets/stock/search?q=').status_code == 400


def test_search_returns_results_with_links(client):
    response = client.get('/api/v1/assets/stock/search?q=apple')
    assert response.status_code == 200
    body = response.get_json()
    assert body['results'][0]['symbol'] == 'AAPL'
    assert '_links' in body['results'][0]


def test_buy_and_sell_asset_round_trip(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 1000})

    buy = client.post(
        f'/api/v1/users/{user["userId"]}/assets/stock/buy',
        json={'ticker': 'AAPL', 'quantity': 5},
    )
    assert buy.status_code == 200

    holdings = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/AAPL/holdings')
    assert holdings.get_json()['shares'] == 5.0

    sell = client.post(
        f'/api/v1/users/{user["userId"]}/assets/stock/sell',
        json={'ticker': 'AAPL', 'quantity': 2},
    )
    assert sell.status_code == 200

    holdings = client.get(f'/api/v1/users/{user["userId"]}/assets/stock/AAPL/holdings')
    assert holdings.get_json()['shares'] == 3.0


def test_buy_rejects_insufficient_funds(client):
    user = register_user(client)
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/stock/buy',
        json={'ticker': 'AAPL', 'quantity': 5},
    )
    assert response.status_code == 400


def test_buy_rejects_missing_ticker(client):
    user = register_user(client)
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/stock/buy',
        json={'quantity': 5},
    )
    assert response.status_code == 400


def test_bond_cannot_be_bought_after_maturity(client, app):
    _add_bond(app, ticker='MBOND')
    with app.app_context():
        session = get_session()
        bond = session.get(Bond, 'MBOND')
        bond.maturityDate = date.today() - timedelta(days=1)
        session.commit()

    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 10000})
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/bond/buy',
        json={'ticker': 'MBOND', 'quantity': 1},
    )
    assert response.status_code == 400


def test_unknown_bond_ticker_cannot_be_bought(client):
    user = register_user(client)
    client.post(f'/api/v1/users/{user["userId"]}/deposit', json={'amount': 10000})
    response = client.post(
        f'/api/v1/users/{user["userId"]}/assets/bond/buy',
        json={'ticker': 'NOPE', 'quantity': 1},
    )
    assert response.status_code == 400


def test_asset_detail_404_for_unknown_ticker(client, monkeypatch):
    monkeypatch.setattr(market_data, 'asset_quote', lambda ticker: None)
    response = client.get('/api/v1/assets/stock/NOPE')
    assert response.status_code == 404
