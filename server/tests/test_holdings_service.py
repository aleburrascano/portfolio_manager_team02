"""
Holdings: what a user still owns, what it cost, and how it is ordered.

The trades are written straight to the database rather than bought through
the routes, because these tests are about the arithmetic over a ledger, and
buying through the routes would price every trade off the live market.
"""
from datetime import datetime
from decimal import Decimal

import pytest

import services.holdings as holdings_service
from db.connection import get_session
from db.models import Asset, AssetTransaction
from services.auth import register


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def user_id(ctx):
    return register('Ada', 'password1', 'Ada', 'Lovelace')['userId']


def record_trade(user_id, ticker, qty, price, asset_type='stock', day=1):
    """Write one trade directly, with `qty` signed the way the schema stores it."""
    session = get_session()
    if session.get(Asset, ticker) is None:
        session.add(Asset(ticker=ticker, assetType=asset_type))
        session.flush()
    session.add(AssetTransaction(
        ticker=ticker,
        qty=Decimal(str(qty)),
        price=Decimal(str(price)),
        assetTransactionType='buy' if Decimal(str(qty)) > 0 else 'sell',
        userId=user_id,
        assetTransactionDate=datetime(2026, 1, day, 12, 0, 0),
    ))
    session.commit()


@pytest.fixture()
def priced_at(monkeypatch):
    """
    Pin every provider's prices, so the maths is the only variable.

    Both quote paths are stubbed: holdings reads the batched live quote
    first (for today's move) and falls back to the valuation price when a
    type doesn't stream. `changes` sets today's per-unit move; it defaults
    to a flat market.
    """
    def _apply(prices, changes=None):
        moves = changes or {}

        def live_quotes(tickers, _p=prices, _c=moves):
            return {
                ticker: {
                    'symbol': ticker,
                    'currentPrice': _p[ticker],
                    'change': _c.get(ticker, 0.0),
                }
                for ticker in tickers
                if ticker in _p
            }

        for provider in holdings_service.PROVIDERS.values():
            monkeypatch.setattr(provider, 'live_quotes', live_quotes)
            monkeypatch.setattr(
                provider, 'valuation_price', lambda ticker, _p=prices: _p.get(ticker, 0.0)
            )
    return _apply


def test_no_trades_returns_empty_book(user_id):
    result = holdings_service.get_holdings(user_id)
    assert result['holdings'] == []
    assert result['totals']['positions'] == 0


def test_position_reports_cost_basis_and_gain(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=100)
    priced_at({'AAPL': 150.0})

    position = holdings_service.get_holdings(user_id)['holdings'][0]
    assert position['quantity'] == 10
    assert position['averageCost'] == 100
    assert position['costBasis'] == 1000
    assert position['value'] == 1500
    assert position['gainLoss'] == 500
    assert position['gainLossPercent'] == 50.0


def test_average_cost_blends_multiple_buys(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'AAPL', qty=10, price=200, day=2)
    priced_at({'AAPL': 200.0})

    position = holdings_service.get_holdings(user_id)['holdings'][0]
    assert position['quantity'] == 20
    assert position['averageCost'] == 150


def test_selling_leaves_the_average_cost_alone(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'AAPL', qty=-4, price=500, day=2)
    priced_at({'AAPL': 100.0})

    position = holdings_service.get_holdings(user_id)['holdings'][0]
    assert position['quantity'] == 6
    assert position['averageCost'] == 100
    assert position['gainLoss'] == 0


def test_closed_positions_are_not_holdings(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=5, price=100, day=1)
    record_trade(user_id, 'AAPL', qty=-5, price=120, day=2)
    priced_at({'AAPL': 120.0})

    assert holdings_service.get_holdings(user_id)['holdings'] == []


def test_an_unpriceable_ticker_still_lists(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=5, price=100)
    priced_at({})

    position = holdings_service.get_holdings(user_id)['holdings'][0]
    assert position['value'] == 0.0
    assert position['gainLoss'] == -500


def test_opens_largest_position_first(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=10, day=1)
    record_trade(user_id, 'MSFT', qty=10, price=100, day=2)
    priced_at({'AAPL': 20.0, 'MSFT': 110.0})

    result = holdings_service.get_holdings(user_id)
    assert [row['ticker'] for row in result['holdings']] == ['MSFT', 'AAPL']


def test_every_sortable_field_is_in_the_payload(user_id, priced_at):
    """The client can only sort locally if the server sends what it sorts on."""
    record_trade(user_id, 'AAPL', qty=10, price=10, day=1)
    priced_at({'AAPL': 20.0})

    position = holdings_service.get_holdings(user_id)['holdings'][0]
    for field in ('ticker', 'assetType', 'quantity', 'averageCost', 'value',
                  'costBasis', 'gainLoss', 'gainLossPercent', 'acquiredAt'):
        assert field in position, f'{field} missing from the holdings payload'


def test_totals_sum_the_book(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=10, day=1)
    record_trade(user_id, 'MSFT', qty=10, price=100, day=2)
    priced_at({'AAPL': 20.0, 'MSFT': 110.0})

    totals = holdings_service.get_holdings(user_id)['totals']
    assert totals['positions'] == 2
    assert totals['costBasis'] == 1100
    assert totals['value'] == 1300
    assert totals['gainLoss'] == 200


def test_todays_move_is_the_book_against_yesterdays_close(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'MSFT', qty=5, price=200, day=1)
    priced_at({'AAPL': 150.0, 'MSFT': 210.0}, changes={'AAPL': 5.0, 'MSFT': -2.0})

    result = holdings_service.get_holdings(user_id)
    by_ticker = {row['ticker']: row for row in result['holdings']}
    assert by_ticker['AAPL']['dayChange'] == 50.0
    assert by_ticker['MSFT']['dayChange'] == -10.0

    totals = result['totals']
    assert totals['value'] == 2550.0
    assert totals['dayChange'] == 40.0
    assert totals['dayChangePercent'] == round(40 / 2510 * 100, 2)


def test_a_flat_market_reports_no_daily_move(user_id, priced_at):
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    priced_at({'AAPL': 150.0})

    totals = holdings_service.get_holdings(user_id)['totals']
    assert totals['dayChange'] == 0.0
    assert totals['dayChangePercent'] == 0.0


def test_holdings_are_scoped_to_one_user(user_id, priced_at):
    other = register('Grace', 'password1', 'Grace', 'Hopper')['userId']
    record_trade(user_id, 'AAPL', qty=10, price=10, day=1)
    record_trade(other, 'MSFT', qty=5, price=100, day=1)
    priced_at({'AAPL': 20.0, 'MSFT': 110.0})

    assert [row['ticker'] for row in holdings_service.get_holdings(user_id)['holdings']] == ['AAPL']
    assert [row['ticker'] for row in holdings_service.get_holdings(other)['holdings']] == ['MSFT']
