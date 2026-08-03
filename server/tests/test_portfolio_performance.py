"""
Portfolio performance: replaying the ledgers forward and valuing what was
held on each date.

Price history is stubbed per ticker so the series is deterministic; the
point of these tests is the replay and the gain/loss arithmetic, not the
market data feed.
"""
from datetime import date, datetime, timedelta

import pytest

import services.holdings as holdings_service
import services.portfolio_performance as perf
from db.connection import get_session
from db.models import CashTransaction
from services.auth import register
from services.user_transactions import get_user_balance
from test_holdings_service import record_trade


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def user_id(ctx):
    return register('Ada', 'password1', 'Ada', 'Lovelace')['userId']


@pytest.fixture()
def history(monkeypatch):
    """
    Stub each provider's daily closes: {ticker: {date: close}}.

    Also stubs the live valuation, because the final series point is priced
    from it. It defaults to the most recent close, so a test that only
    cares about history reads as though the market just closed; pass
    `live={ticker: price}` to move it away from the close on purpose.
    """
    def _apply(prices, live=None):
        def get_history(ticker, _p=prices):
            return [
                {'date': day.isoformat(), 'close': close}
                for day, close in sorted(_p.get(ticker, {}).items())
            ]

        def valuation_price(ticker, _p=prices, _l=live or {}):
            if ticker in _l:
                return _l[ticker]
            closes = _p.get(ticker) or {}
            return float(closes[max(closes)]) if closes else 0.0

        # The holdings service reads the batched quote path, so it is pinned
        # to the same prices - these tests cross-check the two services and
        # would be meaningless if one of them reached the real feed.
        def live_quotes(tickers):
            return {
                ticker: {
                    'symbol': ticker,
                    'currentPrice': valuation_price(ticker),
                    'change': 0.0,
                }
                for ticker in tickers
            }

        for provider in perf.PROVIDERS.values():
            monkeypatch.setattr(provider, 'get_history', get_history)
            monkeypatch.setattr(provider, 'valuation_price', valuation_price)
            monkeypatch.setattr(provider, 'live_quotes', live_quotes)

        # The benchmark goes straight to market_data rather than through a
        # provider, so it needs pinning separately or every test here would
        # reach the real feed for it. Driven by the same dict: a test that
        # cares about the comparison puts SPY in `prices`, and one that
        # doesn't gets no benchmark at all.
        monkeypatch.setattr(
            perf.market_data, 'price_history',
            lambda ticker, period='1y', _p=prices: [
                {'date': day.isoformat(), 'close': close}
                for day, close in sorted(_p.get(ticker, {}).items())
            ],
        )
    return _apply


def deposit(user_id, amount, day):
    session = get_session()
    session.add(CashTransaction(
        userId=user_id,
        amount=amount,
        cashTransactionType='deposit',
        cashTransactionDate=datetime(day.year, day.month, day.day, 9, 0, 0),
    ))
    session.commit()


def test_no_activity_gives_an_empty_series(user_id):
    result = perf.get_portfolio_performance(user_id)
    assert result['series'] == []
    assert result['summary']['gainLossPercent'] == 0.0


def test_cash_only_portfolio_tracks_the_deposit(user_id, history):
    history({})
    deposit(user_id, 1000, date.today() - timedelta(days=2))

    result = perf.get_portfolio_performance(user_id)
    assert result['series'][-1]['portfolioValue'] == 1000.0
    assert result['series'][-1]['cash'] == 1000.0
    assert result['series'][-1]['investedValue'] == 0.0
    # Money moved in is not a gain.
    assert result['summary']['gainLoss'] == 0.0


def test_a_holding_is_valued_at_each_days_close(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 1000, bought)
    record_trade(user_id, 'AAPL', qty=5, price=100, day=1)
    history({'AAPL': {bought: 100.0, bought + timedelta(days=1): 120.0}})

    series = perf.get_portfolio_performance(user_id, days=3650)['series']
    by_date = {point['date']: point for point in series}

    # 5 shares at 100 = 500 invested, 500 cash left over.
    assert by_date['2026-01-01']['investedValue'] == 500.0
    assert by_date['2026-01-01']['portfolioValue'] == 1000.0
    # The next day the price moves; the cash does not.
    assert by_date['2026-01-02']['investedValue'] == 600.0
    assert by_date['2026-01-02']['portfolioValue'] == 1100.0


def test_the_last_close_carries_across_a_market_closure(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 1000, bought)
    record_trade(user_id, 'AAPL', qty=5, price=100, day=1)
    # Only one close, on the day of purchase - every later day has none.
    history({'AAPL': {bought: 100.0}})

    series = perf.get_portfolio_performance(user_id, days=3650)['series']
    # A day with no close holds its value rather than collapsing to cash.
    assert series[-1]['investedValue'] == 500.0


def test_gain_is_measured_against_deposits_not_the_first_point(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 1000, bought)
    record_trade(user_id, 'AAPL', qty=5, price=100, day=1)
    history({'AAPL': {bought: 100.0, bought + timedelta(days=1): 200.0}})

    summary = perf.get_portfolio_performance(user_id, days=3650)['summary']
    # 5 shares now worth 200 each = 1000, plus 500 cash = 1500 against 1000 in.
    assert summary['netDeposits'] == 1000.0
    assert summary['currentValue'] == 1500.0
    assert summary['gainLoss'] == 500.0
    assert summary['gainLossPercent'] == 50.0


def test_a_sale_reduces_the_position_and_returns_the_cash(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 1000, bought)
    record_trade(user_id, 'AAPL', qty=5, price=100, day=1)
    record_trade(user_id, 'AAPL', qty=-5, price=200, day=2)
    history({'AAPL': {bought: 100.0, bought + timedelta(days=1): 200.0}})

    series = perf.get_portfolio_performance(user_id, days=3650)['series']
    final = series[-1]
    assert final['investedValue'] == 0.0
    # 1000 deposited - 500 spent + 1000 returned.
    assert final['cash'] == 1500.0


def test_breakdown_by_asset_type(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 10000, bought)
    record_trade(user_id, 'AAPL', qty=10, price=100, asset_type='stock', day=1)
    record_trade(user_id, 'BTC-USD', qty=1, price=1000, asset_type='crypto', day=1)
    history({
        'AAPL': {bought: 100.0, bought + timedelta(days=1): 150.0},
        'BTC-USD': {bought: 1000.0, bought + timedelta(days=1): 900.0},
    })

    result = perf.get_portfolio_performance(user_id, days=3650)
    by_type = {row['assetType']: row for row in result['byAssetType']}
    assert by_type['stock']['gainLoss'] == 500.0
    assert by_type['stock']['gainLossPercent'] == 50.0
    assert by_type['crypto']['gainLoss'] == -100.0
    assert by_type['crypto']['gainLossPercent'] == -10.0


# The strongest check available: the cash the replay arrives at must equal
# the balance the wallet computes independently in SQL. If the replay ever
# mishandles a sign, double-counts a trade, or drops one, these diverge.
def test_replayed_cash_matches_the_wallet_balance(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 10_000, bought)
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'MSFT', qty=4, price=250, day=2)
    record_trade(user_id, 'AAPL', qty=-3, price=150, day=3)
    deposit(user_id, 500, bought + timedelta(days=4))
    history({
        'AAPL': {bought: 100.0},
        'MSFT': {bought: 250.0},
    })

    series = perf.get_portfolio_performance(user_id, days=3650)['series']
    assert round(series[-1]['cash'], 2) == round(float(get_user_balance(user_id)), 2)


# The dashboard shows the performance headline directly above the holdings
# table. If they disagree the app is telling one user two different things
# about how much money they have, so the two services are pinned together.
def test_the_headline_matches_the_holdings_table(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 10_000, bought)
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'BTC-USD', qty=2, price=500, asset_type='crypto', day=1)
    # The closes are stale on purpose: the final point must follow the live
    # valuation, not the last close it was replayed with.
    history(
        {'AAPL': {bought: 100.0}, 'BTC-USD': {bought: 500.0}},
        live={'AAPL': 175.0, 'BTC-USD': 610.0},
    )

    result = perf.get_portfolio_performance(user_id, days=3650)
    book = holdings_service.get_holdings(user_id)
    balance = float(get_user_balance(user_id))

    assert result['series'][-1]['investedValue'] == book['totals']['value']
    assert result['series'][-1]['portfolioValue'] == round(book['totals']['value'] + balance, 2)
    assert result['summary']['currentValue'] == round(book['totals']['value'] + balance, 2)


def test_the_class_breakdown_adds_up_to_the_headline(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 10_000, bought)
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'BTC-USD', qty=2, price=500, asset_type='crypto', day=1)
    history(
        {'AAPL': {bought: 100.0}, 'BTC-USD': {bought: 500.0}},
        live={'AAPL': 175.0, 'BTC-USD': 610.0},
    )

    result = perf.get_portfolio_performance(user_id, days=3650)
    by_class = sum(row['value'] for row in result['byAssetType'])
    assert round(by_class, 2) == result['series'][-1]['investedValue']


def test_a_ticker_that_cannot_be_priced_falls_back_to_its_last_close(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 10_000, bought)
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    # 0.0 is how valuation_price reports "no price available".
    history({'AAPL': {bought: 120.0}}, live={'AAPL': 0.0})

    result = perf.get_portfolio_performance(user_id, days=3650)
    # The last close, not zero - a blank chart is worse than a stale one.
    assert result['series'][-1]['investedValue'] == 1200.0


def test_a_position_bought_and_sold_leaves_no_value_behind(user_id, history):
    bought = date(2026, 1, 1)
    deposit(user_id, 5_000, bought)
    record_trade(user_id, 'AAPL', qty=10, price=100, day=1)
    record_trade(user_id, 'AAPL', qty=-10, price=100, day=2)
    history({'AAPL': {bought: 100.0}})

    result = perf.get_portfolio_performance(user_id, days=3650)
    assert result['series'][-1]['investedValue'] == 0.0
    # A closed position contributes no bucket to the class breakdown.
    assert result['byAssetType'] == []


def test_the_series_covers_every_day_with_no_gaps(user_id, history):
    start = date.today() - timedelta(days=10)
    deposit(user_id, 1000, start)
    history({})

    series = perf.get_portfolio_performance(user_id, days=365)['series']
    dates = [date.fromisoformat(point['date']) for point in series]
    assert dates == sorted(dates)
    assert dates[-1] == date.today()
    for earlier, later in zip(dates, dates[1:]):
        assert (later - earlier).days == 1


def test_window_limits_the_series_without_losing_earlier_trades(user_id, history):
    long_ago = date.today() - timedelta(days=200)
    deposit(user_id, 1000, long_ago)
    record_trade(user_id, 'AAPL', qty=5, price=100, day=1)
    history({'AAPL': {long_ago: 100.0}})

    result = perf.get_portfolio_performance(user_id, days=30)
    assert len(result['series']) <= 31
    # The position was opened before the window and still shows up in it.
    assert result['series'][0]['investedValue'] == 500.0


# The chart's only comparison was "did I beat my own deposits", which a
# portfolio that merely held cash passes. This is the other one.

def test_benchmark_tracks_a_deposit_into_the_index(user_id, history):
    today = date.today()
    days = [today - timedelta(days=n) for n in (2, 1, 0)]
    history({'SPY': dict(zip(days, (100.0, 110.0, 120.0)))})
    deposit(user_id, 1000, days[0])

    result = perf.get_portfolio_performance(user_id)

    # $1000 in at 100 buys 10 units, worth 1100 then 1200 as it rises.
    assert [point['benchmarkValue'] for point in result['series']] == [1000.0, 1100.0, 1200.0]
    assert result['benchmark'] == {'ticker': 'SPY', 'label': 'S&P 500'}


# A later top-up has to go into the benchmark too, or the comparison
# flatters the portfolio for money the benchmark never received.
def test_benchmark_matches_a_later_deposit(user_id, history):
    today = date.today()
    days = [today - timedelta(days=n) for n in (2, 1, 0)]
    history({'SPY': dict(zip(days, (100.0, 100.0, 200.0)))})
    deposit(user_id, 1000, days[0])
    deposit(user_id, 1000, days[1])

    result = perf.get_portfolio_performance(user_id)

    # 10 units, then 20, then those 20 double.
    assert [point['benchmarkValue'] for point in result['series']] == [1000.0, 2000.0, 4000.0]


def test_benchmark_carries_the_last_close_over_a_closed_market(user_id, history):
    today = date.today()
    days = [today - timedelta(days=n) for n in (2, 1, 0)]
    # No close on the middle day, as at a weekend.
    history({'SPY': {days[0]: 100.0, days[2]: 150.0}})
    deposit(user_id, 1000, days[0])

    result = perf.get_portfolio_performance(user_id)
    assert [point['benchmarkValue'] for point in result['series']] == [1000.0, 1000.0, 1500.0]


def test_an_unpriceable_benchmark_leaves_the_comparison_out(user_id, history):
    history({})  # nothing for SPY
    deposit(user_id, 1000, date.today() - timedelta(days=1))

    result = perf.get_portfolio_performance(user_id)

    # Best-effort like the rest of the chart: no comparison rather than no
    # chart at all.
    assert all('benchmarkValue' not in point for point in result['series'])
    assert result['series']


def test_a_failing_benchmark_lookup_does_not_fail_the_request(user_id, history, monkeypatch):
    history({})
    deposit(user_id, 1000, date.today() - timedelta(days=1))

    def boom(ticker, period='1y'):
        raise RuntimeError('feed down')

    monkeypatch.setattr(perf.market_data, 'price_history', boom)

    result = perf.get_portfolio_performance(user_id)
    assert result['series']
