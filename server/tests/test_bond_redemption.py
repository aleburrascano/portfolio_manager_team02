"""
Paying out bonds that have reached maturity.

A matured bond is priced at par and can no longer be bought, so without
redemption it sits in the holdings table as a frozen position its owner has
to notice and sell by hand.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

import services.bond_redemption as redemption
from db.connection import get_session
from db.models import Asset, Bond
from services.asset_transactions import get_holding_qty, record_trade
from services.auth import register
from services.cash_transactions import deposit_cash
from services.user_transactions import get_user_balance


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def user_id(ctx):
    return register('Ada', 'password1', 'Ada', 'Lovelace')['userId']


def add_bond(ticker, matures_in_days, face_value=1000):
    """A zero-coupon bond, so its price is face value discounted by time."""
    session = get_session()
    session.add(Asset(ticker=ticker, assetType='bond'))
    session.add(Bond(
        ticker=ticker,
        name=f'{ticker} Treasury',
        faceValue=Decimal(str(face_value)),
        couponRate=Decimal('0'),
        marketYield=Decimal('0.04'),
        couponFrequency='annual',
        issueDate=date.today() - timedelta(days=365),
        maturityDate=date.today() + timedelta(days=matures_in_days),
    ))
    session.commit()


def buy(user_id, ticker, quantity, price):
    session = get_session()
    record_trade(session, user_id, ticker, Decimal(str(quantity)), Decimal(str(price)), 'buy')
    session.commit()


def test_a_matured_bond_is_paid_out_at_face_value(user_id):
    add_bond('UST1', matures_in_days=-1, face_value=1000)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 2, 950)

    [payout] = redemption.redeem_matured_bonds()

    assert payout['ticker'] == 'UST1'
    assert payout['quantity'] == 2.0
    assert payout['price'] == 1000.0
    assert payout['proceeds'] == 2000.0


def test_redeeming_closes_the_position_and_returns_the_cash(user_id):
    add_bond('UST1', matures_in_days=-1, face_value=1000)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 2, 950)

    redemption.redeem_matured_bonds()

    assert get_holding_qty(user_id, 'UST1') == 0.0
    # 10000 - 1900 spent + 2000 paid out.
    assert get_user_balance(user_id) == Decimal('10100')


def test_a_bond_that_has_not_matured_is_left_alone(user_id):
    add_bond('UST1', matures_in_days=30)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 2, 950)

    assert redemption.redeem_matured_bonds() == []
    assert get_holding_qty(user_id, 'UST1') == 2.0


def test_a_bond_maturing_today_is_paid_out(user_id):
    add_bond('UST1', matures_in_days=0)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 1, 990)

    assert len(redemption.redeem_matured_bonds()) == 1


# The poller calls this on a timer, so it has to be a no-op once the
# position is closed rather than paying out again on every tick.
def test_redeeming_twice_pays_out_once(user_id):
    add_bond('UST1', matures_in_days=-1)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 2, 950)

    redemption.redeem_matured_bonds()
    balance = get_user_balance(user_id)

    assert redemption.redeem_matured_bonds() == []
    assert get_user_balance(user_id) == balance


def test_a_position_already_sold_is_not_paid_out(user_id):
    add_bond('UST1', matures_in_days=-1)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 2, 950)

    session = get_session()
    record_trade(session, user_id, 'UST1', Decimal('2'), Decimal('1000'), 'sell')
    session.commit()

    assert redemption.redeem_matured_bonds() == []


def test_every_holder_is_paid_out(user_id):
    add_bond('UST1', matures_in_days=-1)
    other_id = register('Grace', 'password1', 'Grace', 'Hopper')['userId']
    for holder in (user_id, other_id):
        deposit_cash(holder, Decimal('10000'))
        buy(holder, 'UST1', 1, 950)

    payouts = redemption.redeem_matured_bonds()
    assert sorted(p['userId'] for p in payouts) == sorted([user_id, other_id])


def test_only_the_matured_bond_is_touched(user_id):
    add_bond('UST1', matures_in_days=-1)
    add_bond('UST2', matures_in_days=30)
    deposit_cash(user_id, Decimal('10000'))
    buy(user_id, 'UST1', 1, 950)
    buy(user_id, 'UST2', 1, 900)

    [payout] = redemption.redeem_matured_bonds()
    assert payout['ticker'] == 'UST1'
    assert get_holding_qty(user_id, 'UST2') == 1.0


# The redemption is an ordinary sale, so it shows up in the history and its
# realised gain is computed by the same code as every other one.
def test_a_redemption_appears_as_a_sale_with_its_gain(client, ctx):
    from services.portfolio_performance import realized_gains_for

    user = register('Bob', 'password1', 'Bob', 'Brown')
    add_bond('UST1', matures_in_days=-1, face_value=1000)
    deposit_cash(user['userId'], Decimal('10000'))
    buy(user['userId'], 'UST1', 2, 950)

    redemption.redeem_matured_bonds()

    gains = realized_gains_for(user['userId'])
    [gain] = list(gains.values())
    # Bought at 950, redeemed at par.
    assert gain['costBasis'] == 1900.0
    assert gain['proceeds'] == 2000.0
    assert gain['gainLoss'] == 100.0
