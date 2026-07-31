from decimal import Decimal

import pytest

import services.asset_transactions as at
import services.market_data as market_data
from services.auth import register
from services.exceptions import (
    InsufficientFunds, InsufficientHoldings, InvalidInput, UnknownUser,
)
from services.cash_transactions import deposit_cash


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def user_id(ctx):
    return register('Ada', 'password1', 'Ada', 'Lovelace')['userId']


@pytest.fixture(autouse=True)
def stub_market_data(monkeypatch):
    """AAPL prices at $10 and is classified as a US-listed stock."""
    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('10.00'))
    monkeypatch.setattr(market_data, 'valuation_price', lambda ticker: 10.00)
    monkeypatch.setattr(
        market_data, 'quote_classification',
        lambda ticker: {'exchange': 'NMS', 'quoteType': 'EQUITY'},
    )


def test_purchase_asset_deducts_cash_and_records_holding(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))

    assert at.get_holding_qty(user_id, 'AAPL') == 5.0


def test_purchase_asset_rejects_insufficient_funds(user_id):
    deposit_cash(user_id, Decimal('10.00'))
    with pytest.raises(InsufficientFunds):
        at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))
    assert at.get_holding_qty(user_id, 'AAPL') == 0.0


def test_purchase_asset_rejects_unknown_user(ctx):
    with pytest.raises(UnknownUser):
        at.purchase_asset(999, 'stock', 'AAPL', Decimal('5'))


def test_purchase_asset_rejects_ticker_registered_under_different_type(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('1'))
    with pytest.raises(InvalidInput):
        at.purchase_asset(user_id, 'crypto', 'AAPL', Decimal('1'))


def test_sell_asset_reduces_holding_and_credits_cash(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))
    at.sell_asset(user_id, 'stock', 'AAPL', Decimal('2'))

    assert at.get_holding_qty(user_id, 'AAPL') == 3.0


def test_sell_asset_rejects_insufficient_holdings(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('1'))
    with pytest.raises(InsufficientHoldings):
        at.sell_asset(user_id, 'stock', 'AAPL', Decimal('2'))


def test_get_portfolio_values_reflects_cash_and_holdings(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))

    portfolio = at.get_portfolio_values(user_id)
    assert portfolio['stock'] == pytest.approx(50.0)
    assert portfolio['cash'] == pytest.approx(950.0)
    assert portfolio['crypto'] == 0.0
    assert portfolio['bond'] == 0.0
