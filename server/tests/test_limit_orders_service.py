from decimal import Decimal

import pytest

import services.asset_transactions as at
import services.limit_orders as lo
import services.market_data as market_data
from services.auth import register
from services.cash_transactions import deposit_cash
from services.exceptions import (
    InsufficientFunds, InsufficientHoldings, InvalidInput, MarketDataUnavailable,
    OrderNotFound, UnknownUser,
)


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


def test_place_limit_order_creates_pending_buy(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))

    assert order.status == 'pending'
    assert order.side == 'buy'


def test_place_limit_order_creates_pending_sell(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))

    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'sell', Decimal('5'), Decimal('12.00'))
    assert order.status == 'pending'
    assert order.side == 'sell'


def test_place_limit_order_rejects_non_stock_asset_type(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    with pytest.raises(InvalidInput):
        lo.place_limit_order(user_id, 'crypto', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))


def test_place_limit_order_rejects_bad_side(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    with pytest.raises(InvalidInput):
        lo.place_limit_order(user_id, 'stock', 'AAPL', 'hold', Decimal('5'), Decimal('8.00'))


def test_place_limit_order_rejects_insufficient_funds(user_id):
    deposit_cash(user_id, Decimal('10.00'))
    with pytest.raises(InsufficientFunds):
        lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))


def test_place_limit_order_rejects_insufficient_holdings(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('1'))
    with pytest.raises(InsufficientHoldings):
        lo.place_limit_order(user_id, 'stock', 'AAPL', 'sell', Decimal('5'), Decimal('12.00'))


def test_place_limit_order_rejects_unknown_user(ctx):
    with pytest.raises(UnknownUser):
        lo.place_limit_order(999, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))


def test_cancel_limit_order_marks_cancelled(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))

    lo.cancel_limit_order(user_id, order.limitOrderId)

    pending = lo.list_limit_orders(user_id, status='pending')
    assert pending == []
    [cancelled] = lo.list_limit_orders(user_id, status='cancelled')
    assert cancelled.resolvedAt is not None


def test_cancel_limit_order_rejects_other_users_order(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))

    other_id = register('Grace', 'password1', 'Grace', 'Hopper')['userId']
    with pytest.raises(OrderNotFound):
        lo.cancel_limit_order(other_id, order.limitOrderId)


def test_cancel_limit_order_rejects_unknown_order(user_id):
    with pytest.raises(OrderNotFound):
        lo.cancel_limit_order(user_id, 999)


def test_cancel_limit_order_rejects_already_resolved(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))
    lo.cancel_limit_order(user_id, order.limitOrderId)

    with pytest.raises(InvalidInput):
        lo.cancel_limit_order(user_id, order.limitOrderId)


def test_list_limit_orders_orders_newest_first_and_filters(user_id):
    deposit_cash(user_id, Decimal('1000.00'))
    first = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('1'), Decimal('8.00'))
    second = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('1'), Decimal('7.00'))
    lo.cancel_limit_order(user_id, first.limitOrderId)

    all_orders = lo.list_limit_orders(user_id)
    assert [o.limitOrderId for o in all_orders] == [second.limitOrderId, first.limitOrderId]

    pending = lo.list_limit_orders(user_id, status='pending')
    assert [o.limitOrderId for o in pending] == [second.limitOrderId]


def test_evaluate_pending_orders_fills_buy_when_price_at_or_below_limit(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('1000.00'))
    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('12.00'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('9.00'))
    filled = lo.evaluate_pending_orders()

    assert filled == 1
    refreshed = lo.list_limit_orders(user_id, status='filled')[0]
    assert refreshed.limitOrderId == order.limitOrderId
    assert refreshed.assetTransactionId is not None
    assert at.get_holding_qty(user_id, 'AAPL') == 5.0


def test_evaluate_pending_orders_leaves_buy_pending_when_price_above_limit(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('1000.00'))
    lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('8.00'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('9.00'))
    filled = lo.evaluate_pending_orders()

    assert filled == 0
    assert len(lo.list_limit_orders(user_id, status='pending')) == 1
    assert at.get_holding_qty(user_id, 'AAPL') == 0.0


def test_evaluate_pending_orders_fills_sell_when_price_at_or_above_limit(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))
    order = lo.place_limit_order(user_id, 'stock', 'AAPL', 'sell', Decimal('5'), Decimal('12.00'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('15.00'))
    filled = lo.evaluate_pending_orders()

    assert filled == 1
    refreshed = lo.list_limit_orders(user_id, status='filled')[0]
    assert refreshed.limitOrderId == order.limitOrderId
    assert at.get_holding_qty(user_id, 'AAPL') == 0.0


def test_evaluate_pending_orders_leaves_order_pending_on_insufficient_funds_at_fill(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('100.00'))
    lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('5'), Decimal('12.00'))

    # Spend the cash elsewhere before the poller ticks.
    at.purchase_asset(user_id, 'stock', 'MSFT', Decimal('6'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('10.00'))
    filled = lo.evaluate_pending_orders()

    assert filled == 0
    pending = lo.list_limit_orders(user_id, status='pending')
    assert len(pending) == 1


def test_evaluate_pending_orders_leaves_order_pending_on_insufficient_holdings_at_fill(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('1000.00'))
    at.purchase_asset(user_id, 'stock', 'AAPL', Decimal('5'))
    lo.place_limit_order(user_id, 'stock', 'AAPL', 'sell', Decimal('5'), Decimal('8.00'))

    # Sell the shares elsewhere before the poller ticks.
    at.sell_asset(user_id, 'stock', 'AAPL', Decimal('5'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('9.00'))
    filled = lo.evaluate_pending_orders()

    assert filled == 0
    pending = lo.list_limit_orders(user_id, status='pending')
    assert len(pending) == 1


def test_evaluate_pending_orders_only_fills_what_can_be_afforded_in_one_pass(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('100.00'))
    # Each is affordable at placement (9*11=99 <= 100), and each is
    # affordable alone at the fill price (9*10=90 <= 100) - but not both.
    first = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('9'), Decimal('11.00'))
    second = lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('9'), Decimal('11.00'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('10.00'))
    filled = lo.evaluate_pending_orders()

    assert filled == 1
    statuses = {o.limitOrderId: o.status for o in lo.list_limit_orders(user_id)}
    assert statuses[first.limitOrderId] == 'filled'
    assert statuses[second.limitOrderId] == 'pending'


def test_evaluate_pending_orders_returns_fill_count(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('1000.00'))
    lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('1'), Decimal('12.00'))
    lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('1'), Decimal('12.00'))

    monkeypatch.setattr(market_data, 'trade_price', lambda ticker: Decimal('9.00'))
    assert lo.evaluate_pending_orders() == 2


def test_evaluate_pending_orders_skips_ticker_when_market_data_unavailable(user_id, monkeypatch):
    deposit_cash(user_id, Decimal('1000.00'))
    lo.place_limit_order(user_id, 'stock', 'AAPL', 'buy', Decimal('1'), Decimal('12.00'))
    lo.place_limit_order(user_id, 'stock', 'MSFT', 'buy', Decimal('1'), Decimal('12.00'))

    def flaky_price(ticker):
        if ticker == 'AAPL':
            raise MarketDataUnavailable('down')
        return Decimal('9.00')

    monkeypatch.setattr(market_data, 'trade_price', flaky_price)
    filled = lo.evaluate_pending_orders()

    assert filled == 1
    statuses = {o.ticker: o.status for o in lo.list_limit_orders(user_id)}
    assert statuses['AAPL'] == 'pending'
    assert statuses['MSFT'] == 'filled'
