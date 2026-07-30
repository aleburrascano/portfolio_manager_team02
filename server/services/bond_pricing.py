"""
Bond pricing is computed as the present value of its remaining coupon payments plus face value, 
discounted at its fixed `marketYield`.
"""
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Optional

import db.connection as db_conn

PERIODS_PER_YEAR = {'annual': 1, 'semiannual': 2}

def _as_date(value) -> date:
    return value.date() if hasattr(value, 'date') else value

def get_bond(ticker: str) -> Optional[dict]:
    """Look up one bond's catalog row by ticker"""
    db = db_conn.get_db()
    if db is None:
        return None

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Bonds WHERE ticker = %s", (ticker,))
    row = cursor.fetchone()
    cursor.close()
    return row


def list_bonds() -> list[dict]:
    """The full bond catalog."""
    db = db_conn.get_db()
    if db is None:
        return []

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Bonds ORDER BY maturityDate")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def search_bonds(query: str) -> list[dict]:
    """Bonds whose ticker or name contains the query."""
    db = db_conn.get_db()
    if db is None:
        return []

    like = f"%{query}%"
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM Bonds WHERE ticker LIKE %s OR name LIKE %s ORDER BY maturityDate",
        (like, like),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


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
        return face_value.quantize(Decimal('0.00000001'))

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
        return (coupon * n + face_value).quantize(Decimal('0.00000001'))

    discount = (1 + y) ** -n
    pv_coupons = coupon * (1 - discount) / y
    pv_face = face_value * discount
    return (pv_coupons + pv_face).quantize(Decimal('0.00000001'))


def price_history(bond: dict, days: int = 365) -> list[dict]:
    """Daily closing prices for the trailing 365 days."""
    today = date.today()
    history = []
    for offset in range(days, -1, -1):
        as_of = today - timedelta(days=offset)
        history.append({'date': as_of.strftime('%Y-%m-%d'), 'close': float(price_bond(bond, as_of))})
    return history
