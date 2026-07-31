"""
Seed a demo user with ~2 years of cash and asset transaction history, for
demoing the dashboard's portfolio composition and performance-over-time
graphs. Prices are pulled from real yfinance daily history so the resulting
portfolio value curve looks realistic; transaction dates/amounts are
generated with Faker.

Usage (from the server/ directory):
    python -m scripts.seed [--username demo] [--password demopassword]
                      [--first Demo] [--last User] [--days 730]

Re-running clears and regenerates that user's transactions, so it's safe to
run repeatedly while iterating on the demo.
"""
import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

import pandas as pd

import services.bond_pricing as bond_pricing
import services.market_data as market_data
from db.connection import get_engine, init_db
from db.models import Asset, AssetTransaction, Bond, CashTransaction, User

STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA']
CRYPTOS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
MARKET_TICKERS = {t: 'stock' for t in STOCKS} | {t: 'crypto' for t in CRYPTOS}
# How many bonds from the catalog to trade, so the demo portfolio has a
# bond bucket - the composition donut and the per-class gain/loss both have
# one, and without any holdings they render a hole.
BOND_COUNT = 3

INITIAL_DEPOSIT_RANGE = (30_000, 60_000)
EVENT_SPACING_DAYS = (4, 12)  # roughly one transaction every 4-12 days
DEPOSIT_RANGE = (500, 8_000)
WITHDRAW_RANGE = (200, 3_000)
BUY_DOLLAR_RANGE = (500, 6_000)
SELL_FRACTION_RANGE = (0.1, 0.6)
CASH_RESERVE = Decimal('2000')  # keep a cash cushion so buys don't drain the wallet to zero
EVENT_WEIGHTS = {'buy': 0.45, 'deposit': 0.30, 'sell': 0.15, 'withdraw': 0.10}


def find_or_create_user(session, username, password, first_name, last_name):
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            firstName=first_name,
            lastName=last_name,
            passwordHash=generate_password_hash(password),
        )
        session.add(user)
        session.commit()
    return user.userId


def pick_bonds(session, today):
    """
    Up to BOND_COUNT unmatured bonds from the catalog, as {ticker: dict}.

    Read through the model rather than services.bond_pricing, which reads
    the Flask request-scoped session this script doesn't have.
    """
    bonds = session.scalars(select(Bond).order_by(Bond.maturityDate)).all()
    chosen = {}
    for bond in bonds:
        if bond_pricing._as_date(bond.maturityDate) <= today:
            continue
        chosen[bond.ticker] = bond_pricing._serialize(bond)
        if len(chosen) == BOND_COUNT:
            break
    return chosen


def bond_close_series(bond, start, days):
    """
    A bond's daily price as a pandas Series, so it looks up exactly like a
    yfinance close series does. Bonds are priced from their own terms at any
    date, so this is computed rather than fetched.
    """
    dates = [start + timedelta(days=offset) for offset in range(days + 1)]
    return pd.Series(
        [float(bond_pricing.price_bond(bond, day.date())) for day in dates],
        index=pd.DatetimeIndex(dates),
    )


def register_assets(session, tickers):
    """Assets have to exist before transactions can reference them."""
    for ticker, asset_type in tickers.items():
        if session.get(Asset, ticker) is None:
            session.add(Asset(ticker=ticker, assetType=asset_type))
    session.commit()


def clear_user_transactions(session, user_id):
    session.execute(delete(CashTransaction).where(CashTransaction.userId == user_id))
    session.execute(delete(AssetTransaction).where(AssetTransaction.userId == user_id))
    session.commit()


def fetch_price_histories(tickers, days):
    histories = {}
    for ticker in tickers:
        closes = market_data.close_series(ticker, days + 10)
        if closes is None:
            print(f"warning: no price history for {ticker}, skipping it", file=sys.stderr)
            continue
        histories[ticker] = closes
    if not histories:
        raise RuntimeError("no price history could be fetched for any ticker")
    return histories


def price_on_or_before(series, when):
    idx = series.index.searchsorted(when, side='right') - 1
    if idx < 0:
        idx = 0
    return series.index[idx], float(series.iloc[idx])


def build_events(fake, start, end):
    events = []
    current = start
    while current < end:
        current += timedelta(days=random.randint(*EVENT_SPACING_DAYS))
        if current >= end:
            break
        when = fake.date_time_between(start_date=current, end_date=current + timedelta(days=1))
        events.append(when)
    return events


def run(username, password, first_name, last_name, days):
    fake = Faker()
    load_dotenv()
    init_db()
    session = Session(get_engine())

    user_id = find_or_create_user(session, username, password, first_name, last_name)

    # UTC, to match the clock the database writes its own defaults on.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=days)

    bonds = pick_bonds(session, now.date())
    tickers = MARKET_TICKERS | {ticker: 'bond' for ticker in bonds}
    register_assets(session, tickers)
    clear_user_transactions(session, user_id)

    histories = fetch_price_histories(MARKET_TICKERS.keys(), days)
    for ticker, bond in bonds.items():
        histories[ticker] = bond_close_series(bond, start, days)
    available_tickers = list(histories.keys())

    cash_rows = []
    asset_rows = []
    cash_balance = Decimal('0')
    holdings = {t: Decimal('0') for t in available_tickers}

    initial_deposit = Decimal(str(random.randint(*INITIAL_DEPOSIT_RANGE)))
    cash_rows.append(('deposit', initial_deposit, start))
    cash_balance += initial_deposit

    for when in build_events(fake, start, now):
        held = [t for t, qty in holdings.items() if qty > 0]
        weights = dict(EVENT_WEIGHTS)
        if not held:
            weights.pop('sell', None)
        kind = random.choices(list(weights.keys()), weights=list(weights.values()))[0]

        if kind == 'deposit':
            amount = Decimal(str(random.randint(*DEPOSIT_RANGE)))
            cash_rows.append(('deposit', amount, when))
            cash_balance += amount

        elif kind == 'withdraw':
            amount = Decimal(str(random.randint(*WITHDRAW_RANGE)))
            if amount > cash_balance:
                continue
            cash_rows.append(('withdraw', -amount, when))
            cash_balance -= amount

        elif kind == 'buy':
            ticker = random.choice(available_tickers)
            _, price = price_on_or_before(histories[ticker], when)
            price = Decimal(str(round(price, 4)))
            available_cash = cash_balance - CASH_RESERVE
            dollar_amount = Decimal(str(random.randint(*BUY_DOLLAR_RANGE)))
            if dollar_amount > available_cash:
                dollar_amount = available_cash
            if dollar_amount <= 0 or price <= 0:
                continue
            qty = (dollar_amount / price).quantize(Decimal('0.000001'))
            if qty <= 0:
                continue
            cost = (qty * price).quantize(Decimal('0.00000001'))
            asset_rows.append((ticker, qty, price, 'buy', when))
            cash_balance -= cost
            holdings[ticker] += qty

        elif kind == 'sell':
            ticker = random.choice(held)
            _, price = price_on_or_before(histories[ticker], when)
            price = Decimal(str(round(price, 4)))
            fraction = Decimal(str(round(random.uniform(*SELL_FRACTION_RANGE), 4)))
            qty = (holdings[ticker] * fraction).quantize(Decimal('0.000001'))
            if qty <= 0:
                continue
            proceeds = (qty * price).quantize(Decimal('0.00000001'))
            asset_rows.append((ticker, -qty, price, 'sell', when))
            cash_balance += proceeds
            holdings[ticker] -= qty

    session.add_all([
        CashTransaction(
            cashTransactionType=kind, amount=amount,
            cashTransactionDate=when, userId=user_id,
        )
        for kind, amount, when in cash_rows
    ])
    session.add_all([
        AssetTransaction(
            ticker=ticker, qty=qty, price=price,
            assetTransactionType=kind, assetTransactionDate=when, userId=user_id,
        )
        for ticker, qty, price, kind, when in asset_rows
    ])
    session.commit()
    session.close()

    print(f"Seeded user {first_name} {last_name} (userId={user_id}, login: {username} / {password})")
    print(f"  {len(cash_rows)} cash transactions, {len(asset_rows)} asset transactions")
    print(f"  final cash balance: ${cash_balance:,.2f}")
    print("  final holdings:")
    for ticker, qty in holdings.items():
        if qty > 0:
            print(f"    {ticker}: {qty}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', default='demo')
    parser.add_argument('--password', default='demopassword')
    parser.add_argument('--first', default='Demo')
    parser.add_argument('--last', default='User')
    parser.add_argument('--days', type=int, default=730)
    args = parser.parse_args()
    run(args.username, args.password, args.first, args.last, args.days)
