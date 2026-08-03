from datetime import date, timedelta
from decimal import Decimal

import pytest

from db.connection import get_session
from db.models import Asset, Bond
import services.bond_pricing as bp
from services.exceptions import MarketDataUnavailable


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


def _add_bond(**overrides):
    defaults = dict(
        ticker='TBOND',
        name='Test Bond',
        faceValue=Decimal('1000'),
        couponRate=Decimal('0.05'),
        marketYield=Decimal('0.05'),
        couponFrequency='semiannual',
        issueDate=date.today() - timedelta(days=365),
        maturityDate=date.today() + timedelta(days=365),
    )
    defaults.update(overrides)
    session = get_session()
    session.add(Asset(ticker=defaults['ticker'], assetType='bond'))
    session.add(Bond(**defaults))
    session.commit()
    return defaults


def test_get_bond_returns_none_for_unknown_ticker(ctx):
    assert bp.get_bond('NOPE') is None


def test_get_bond_returns_catalog_row(ctx):
    _add_bond()
    bond = bp.get_bond('TBOND')
    assert bond['ticker'] == 'TBOND'
    assert bond['name'] == 'Test Bond'


def test_search_bonds_matches_ticker_or_name(ctx):
    _add_bond(ticker='ABC1', name='Alpha Bond')
    _add_bond(ticker='XYZ1', name='Zeta Note')
    assert [b['ticker'] for b in bp.search_bonds('Alpha')] == ['ABC1']
    assert [b['ticker'] for b in bp.search_bonds('XYZ1')] == ['XYZ1']
    assert bp.search_bonds('nonexistent') == []


def test_is_matured_true_at_and_after_maturity(ctx):
    bond = _add_bond(maturityDate=date(2020, 1, 1))
    assert bp.is_matured(bond, date(2020, 1, 1)) is True
    assert bp.is_matured(bond, date(2020, 1, 2)) is True
    assert bp.is_matured(bond, date(2019, 12, 31)) is False


def test_price_bond_returns_face_value_at_maturity(ctx):
    bond = _add_bond(maturityDate=date(2025, 6, 1), faceValue=Decimal('1000'))
    assert bp.price_bond(bond, date(2025, 6, 1)) == Decimal('1000.00000000')


def test_price_bond_at_par_when_coupon_equals_yield(ctx):
    """A bond priced at its own coupon rate should trade at (about) face value."""
    bond = _add_bond(
        faceValue=Decimal('1000'), couponRate=Decimal('0.05'), marketYield=Decimal('0.05'),
        issueDate=date.today() - timedelta(days=1), maturityDate=date.today() + timedelta(days=365 * 5),
    )
    price = bp.price_bond(bond, date.today())
    assert price == pytest.approx(Decimal('1000'), abs=Decimal('5'))


def test_price_bond_zero_yield_is_undiscounted_sum(ctx):
    bond = _add_bond(
        faceValue=Decimal('1000'), couponRate=Decimal('0.05'), marketYield=Decimal('0'),
        couponFrequency='annual',
        issueDate=date.today(), maturityDate=date.today() + timedelta(days=365),
    )
    price = bp.price_bond(bond, date.today())
    assert price == Decimal('1050.00000000')


def test_price_history_spans_the_requested_days(ctx):
    bond = _add_bond()
    history = bp.price_history(bond, days=10)
    assert len(history) == 11
    assert history[-1]['date'] == date.today().strftime('%Y-%m-%d')


def test_trade_price_raises_for_unknown_ticker(ctx):
    with pytest.raises(MarketDataUnavailable):
        bp.trade_price('NOPE')


def test_trade_price_matches_price_bond_today(ctx):
    _add_bond()
    assert bp.trade_price('TBOND') == bp.price_bond(bp.get_bond('TBOND'))
