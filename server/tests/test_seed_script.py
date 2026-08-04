"""
The demo seeder.

It had no tests, which is how it shipped for months creating accounts that
could not be signed into. These cover the parts that have to agree with the
rest of the app - the username form login looks for, and the shapes the
services expect - rather than the generated history, which is random by
design.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

import scripts.seed as seed
import services.bond_pricing as bond_pricing
from db.connection import get_session
from db.models import Asset, AssetTransaction, Bond, LimitOrder, User, WatchlistEntry
from services.auth import authenticate


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def session(ctx):
    return get_session()


def price_series(unit):
    """Three daily closes on an index of the given resolution."""
    index = pd.DatetimeIndex(
        [datetime(2026, 1, day) for day in (1, 2, 3)]
    ).as_unit(unit)
    return pd.Series([100.0, 110.0, 120.0], index=index)


@pytest.mark.parametrize('unit', ['s', 'ms', 'us', 'ns'])
def test_a_price_is_found_whatever_resolution_the_index_carries(unit):
    """
    The seed died partway through against production's pandas, which gives
    yfinance's daily bars a second-resolution index. Event times carry
    microseconds, and pandas raises "Cannot losslessly convert units"
    rather than truncating - so a run that worked on one machine failed on
    another with no code difference between them.
    """
    when = datetime(2026, 1, 2, 15, 30, 45, 123456)

    found, price = seed.price_on_or_before(price_series(unit), when)

    assert price == 110.0
    assert found.date() == date(2026, 1, 2)


def test_a_price_before_any_close_falls_back_to_the_first(session):
    found, price = seed.price_on_or_before(price_series('s'), datetime(2025, 6, 1))

    assert price == 100.0
    assert found.date() == date(2026, 1, 1)


def test_the_username_is_stored_in_the_form_login_looks_for(session):
    user_id, username = seed.find_or_create_user(session, 'Demo', 'password1', 'Ada', 'Lovelace')

    assert username == 'demo'
    assert session.get(User, user_id).username == 'demo'


def test_a_seeded_account_can_actually_log_in(session):
    seed.find_or_create_user(session, '  MixedCase  ', 'password1', 'Ada', 'Lovelace')

    assert authenticate('MixedCase', 'password1') is not None
    assert authenticate('mixedcase', 'password1') is not None


def test_seeding_the_same_user_twice_reuses_the_account(session):
    first, _ = seed.find_or_create_user(session, 'Demo', 'password1', 'Ada', 'Lovelace')
    second, _ = seed.find_or_create_user(session, 'demo', 'password1', 'Ada', 'Lovelace')

    assert first == second


def add_bond(session, ticker, matures_in_days):
    session.add(Asset(ticker=ticker, assetType='bond'))
    session.add(Bond(
        ticker=ticker, name=f'{ticker} Treasury', faceValue=Decimal('1000'),
        couponRate=Decimal('0.04'), marketYield=Decimal('0.04'), couponFrequency='annual',
        issueDate=date.today() - timedelta(days=365),
        maturityDate=date.today() + timedelta(days=matures_in_days),
    ))
    session.commit()


def test_pick_bonds_returns_priceable_terms(session):
    add_bond(session, 'UST1', matures_in_days=400)

    chosen = seed.pick_bonds(session, date.today())

    assert bond_pricing.price_bond(chosen['UST1']) > 0


def test_pick_bonds_skips_matured_ones(session):
    add_bond(session, 'OLD', matures_in_days=-1)
    add_bond(session, 'NEW', matures_in_days=400)

    assert list(seed.pick_bonds(session, date.today())) == ['NEW']


def test_the_watchlist_is_ordered_newest_first(session):
    user_id, _ = seed.find_or_create_user(session, 'demo', 'password1', 'Ada', 'Lovelace')
    now = datetime(2026, 6, 1, 12, 0, 0)

    seed.seed_watchlist(session, user_id, {'AAPL': 'stock', 'MSFT': 'stock'}, now)

    entries = session.query(WatchlistEntry).all()
    by_ticker = {e.ticker: e.addedAt for e in entries}
    assert by_ticker['AAPL'] > by_ticker['MSFT']


def test_orders_are_seeded_in_every_status(session):
    user_id, _ = seed.find_or_create_user(session, 'demo', 'password1', 'Ada', 'Lovelace')
    session.add(Asset(ticker='AAPL', assetType='stock'))
    session.add(Asset(ticker='MSFT', assetType='stock'))
    session.commit()

    count = seed.seed_orders(
        session, user_id, {'AAPL': Decimal('100'), 'MSFT': Decimal('200')}, datetime.now(),
    )

    statuses = {o.status for o in session.query(LimitOrder).all()}
    assert count >= 3
    assert statuses == {'pending', 'cancelled'} or statuses == {'pending', 'filled', 'cancelled'}


def test_pending_orders_are_placed_far_from_the_market(session):
    user_id, _ = seed.find_or_create_user(session, 'demo', 'password1', 'Ada', 'Lovelace')
    session.add(Asset(ticker='AAPL', assetType='stock'))
    session.commit()

    seed.seed_orders(session, user_id, {'AAPL': Decimal('100')}, datetime.now())

    for order in session.query(LimitOrder).filter_by(status='pending').all():
        assert order.limitPrice < Decimal('100')


def test_a_filled_order_points_at_a_real_trade(session):
    user_id, _ = seed.find_or_create_user(session, 'demo', 'password1', 'Ada', 'Lovelace')
    session.add(Asset(ticker='AAPL', assetType='stock'))
    session.add(AssetTransaction(
        ticker='AAPL', qty=Decimal('5'), price=Decimal('100'),
        assetTransactionType='buy', assetTransactionDate=datetime(2026, 5, 1), userId=user_id,
    ))
    session.commit()

    seed.seed_orders(session, user_id, {'AAPL': Decimal('100')}, datetime.now())

    [filled] = session.query(LimitOrder).filter_by(status='filled').all()
    trade = session.get(AssetTransaction, filled.assetTransactionId)
    assert trade is not None and trade.ticker == filled.ticker


def test_bonds_get_no_conditional_orders(session):
    user_id, _ = seed.find_or_create_user(session, 'demo', 'password1', 'Ada', 'Lovelace')
    add_bond(session, 'UST1', matures_in_days=400)

    assert seed.seed_orders(session, user_id, {'UST1': Decimal('980')}, datetime.now()) == 0
