"""
Bond pricing is computed as the present value of its remaining coupon
payments plus face value, discounted at its fixed `marketYield`.

The catalog is reference data rather than a live feed - bonds are not
quoted anywhere, so their price is derived from their terms and the date.
"""
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import List, Optional

from sqlalchemy import or_, select

from db.connection import get_session
from db.models import Bond
from services.exceptions import MarketDataUnavailable

PERIODS_PER_YEAR = {'annual': 1, 'semiannual': 2}
CENTS = Decimal('0.00000001')


def _as_date(value) -> date:
    return value.date() if hasattr(value, 'date') else value


def _serialize(bond: Bond) -> dict:
    return {
        'ticker': bond.ticker,
        'name': bond.name,
        'faceValue': bond.faceValue,
        'couponRate': bond.couponRate,
        'marketYield': bond.marketYield,
        'couponFrequency': bond.couponFrequency,
        'issueDate': bond.issueDate,
        'maturityDate': bond.maturityDate,
    }


def get_bond(ticker: str) -> Optional[dict]:
    """Look up one bond's catalog row by ticker."""
    bond = get_session().get(Bond, ticker)
    return _serialize(bond) if bond else None


def list_bonds() -> List[dict]:
    """The full bond catalog."""
    bonds = get_session().scalars(select(Bond).order_by(Bond.maturityDate))
    return [_serialize(bond) for bond in bonds]


def search_bonds(query: str) -> List[dict]:
    """Bonds whose ticker or name contains the query."""
    like = f'%{query}%'
    bonds = get_session().scalars(
        select(Bond)
        .where(or_(Bond.ticker.like(like), Bond.name.like(like)))
        .order_by(Bond.maturityDate)
    )
    return [_serialize(bond) for bond in bonds]


def is_matured(bond: dict, as_of: Optional[date] = None) -> bool:
    as_of = as_of or date.today()
    return as_of >= _as_date(bond['maturityDate'])


def price_bond(bond: dict, as_of: Optional[date] = None) -> Decimal:
    """
    Present-value price of a bond's remaining cash flows, discounted at its
    fixed market yield. Returns face value at or after maturity.
    """
    as_of = as_of or date.today()
    face_value = Decimal(str(bond['faceValue']))
    maturity = _as_date(bond['maturityDate'])

    if as_of >= maturity:
        return face_value.quantize(CENTS)

    periods_per_year = PERIODS_PER_YEAR[bond['couponFrequency']]
    coupon_rate = Decimal(str(bond['couponRate']))
    market_yield = Decimal(str(bond['marketYield']))

    coupon = face_value * coupon_rate / periods_per_year
    y = market_yield / periods_per_year

    period_days = Decimal('365.25') / periods_per_year
    days_remaining = Decimal((maturity - as_of).days)
    n = int((days_remaining / period_days).to_integral_value(rounding=ROUND_CEILING))
    n = max(n, 1)

    if y == 0:
        return (coupon * n + face_value).quantize(CENTS)

    discount = (1 + y) ** -n
    pv_coupons = coupon * (1 - discount) / y
    pv_face = face_value * discount
    return (pv_coupons + pv_face).quantize(CENTS)


def price_history(bond: dict, days: int = 365) -> List[dict]:
    """Daily closing prices for the trailing 365 days."""
    today = date.today()
    return [
        {
            'date': (today - timedelta(days=offset)).strftime('%Y-%m-%d'),
            'close': float(price_bond(bond, today - timedelta(days=offset))),
        }
        for offset in range(days, -1, -1)
    ]


def trade_price(ticker: str) -> Decimal:
    """
    The price to execute a bond trade at.

    Raises:
        MarketDataUnavailable: if the ticker isn't in the catalog, matching
        how an unpriceable stock or crypto is reported.
    """
    bond = get_bond(ticker)
    if bond is None:
        raise MarketDataUnavailable(f'No price available for {ticker}.')
    return price_bond(bond)
