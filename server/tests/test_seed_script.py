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


# The bug this file exists for: services.auth lowercases on the way in, and
# the seeder inserted the raw string - so `--username Demo` stored "Demo"
# while every login looked for "demo".
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

    # The dict has to be the shape bond_pricing takes, or the seeded price
    # series would differ from what the app shows for the same bond.
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
    # Staggered, so two rows written in the same second still order.
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


# A demo whose open orders fill as soon as the poller notices them shows an
# empty tab to anyone who looks a minute later.
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

    # A bond is priced from its own terms on a schedule, so it takes no
    # conditional order - the seeder asks the registry rather than assuming.
    assert seed.seed_orders(session, user_id, {'UST1': Decimal('980')}, datetime.now()) == 0
