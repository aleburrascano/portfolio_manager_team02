from decimal import Decimal

import pytest

import services.cash_transactions as ct
from services.auth import register
from services.exceptions import InsufficientFunds, UnknownUser
from services.user_transactions import get_user_balance


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def user_id(ctx):
    return register('Ada', 'password1', 'Ada', 'Lovelace')['userId']


def test_deposit_increases_balance(user_id):
    ct.deposit_cash(user_id, Decimal('100.00'))
    assert get_user_balance(user_id) == Decimal('100.00')


def test_withdraw_decreases_balance(user_id):
    ct.deposit_cash(user_id, Decimal('100.00'))
    ct.withdraw_cash(user_id, Decimal('40.00'))
    assert get_user_balance(user_id) == Decimal('60.00')


def test_withdraw_rejects_insufficient_funds(user_id):
    ct.deposit_cash(user_id, Decimal('10.00'))
    with pytest.raises(InsufficientFunds):
        ct.withdraw_cash(user_id, Decimal('10.01'))
    assert get_user_balance(user_id) == Decimal('10.00')


def test_withdraw_rejects_unknown_user(ctx):
    with pytest.raises(UnknownUser):
        ct.withdraw_cash(999, Decimal('1.00'))
