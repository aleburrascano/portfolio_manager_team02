"""
Paying out bonds that have reached maturity.

A bond's price converges to its face value as the maturity date approaches
- that is what price_bond computes - so by the time it matures the position
is worth par and stops moving. Without this it would sit in the holdings
table forever: can_trade refuses to let anyone buy more of it, nothing pays
it out, and the only way to get the money back is to notice and sell it by
hand. That is not what holding a bond to maturity means.

Redeeming is a sale at face value, booked as an ordinary AssetTransaction,
so the cash lands in the balance and the trade shows up in the history like
any other. Nothing new is needed to represent it, and the realised gain on
it is computed by the same code that handles every other sale.

Driven by the poller rather than by a request, for the same reason limit
orders are: a bond matures on a date, not when its owner next opens the app.
"""
import logging
from datetime import date
from typing import List

from sqlalchemy import func, select

import db.connection as db_conn
import services.bond_pricing as bond_pricing
from db.models import AssetTransaction, Bond
from services.asset_transactions import record_trade

logger = logging.getLogger(__name__)


def _matured_tickers(session, as_of: date) -> List[str]:
    return list(session.scalars(
        select(Bond.ticker).where(Bond.maturityDate <= as_of)
    ).all())


def _holders_of(session, ticker: str):
    """
    Every user still holding this ticker, as (userId, quantity).

    Summed in the database: a matured bond may have been traded by anyone,
    and pulling each user's ledger to find out who still has some would
    scale with the whole history rather than with the answer.
    """
    return session.execute(
        select(AssetTransaction.userId, func.sum(AssetTransaction.qty))
        .where(AssetTransaction.ticker == ticker)
        .group_by(AssetTransaction.userId)
        .having(func.sum(AssetTransaction.qty) > 0)
    ).all()


def redeem_matured_bonds(as_of: date = None) -> List[dict]:
    """
    Pay out every open position in a bond that has reached maturity.

    Each redemption is committed on its own, under the holder's row lock, so
    one that fails - or one user's slow lock - can't stop the others. Safe
    to run on a timer: once a position is paid out it is closed, so the next
    pass finds nothing for it.

    Returns:
        list[dict]: one row per redemption, describing what was paid out.
    """
    as_of = as_of or date.today()
    session = db_conn.get_session()

    redeemed = []
    for ticker in _matured_tickers(session, as_of):
        bond = bond_pricing.get_bond(ticker)
        if bond is None:
            continue
        price = bond_pricing.price_bond(bond, as_of)

        for user_id, quantity in _holders_of(session, ticker):
            payout = _redeem_one(session, user_id, ticker, quantity, price)
            if payout is not None:
                redeemed.append(payout)

    return redeemed


def _redeem_one(session, user_id: int, ticker: str, quantity, price) -> dict:
    """Close one holder's position at face value, under their row lock."""
    try:
        if not db_conn.lock_user(session, user_id):
            return None

        held = session.scalar(
            select(func.coalesce(func.sum(AssetTransaction.qty), 0))
            .where(AssetTransaction.userId == user_id, AssetTransaction.ticker == ticker)
        )
        if not held or held <= 0:
            return None

        record_trade(session, user_id, ticker, held, price, 'sell')
        session.commit()
        return {
            'userId': user_id,
            'ticker': ticker,
            'quantity': float(held),
            'price': float(price),
            'proceeds': float(held * price),
        }
    except Exception:
        logger.exception('Could not redeem %s for user %s', ticker, user_id)
        session.rollback()
        return None
