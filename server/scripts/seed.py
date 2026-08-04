"""
Seed a demo user with ~2 years of cash and asset transaction history, for
demoing the dashboard's portfolio composition and performance-over-time
graphs. Prices are pulled from real yfinance daily history so the resulting
portfolio value curve looks realistic; transaction dates/amounts are
generated with Faker.

Usage (from the server/ directory):
    python -m scripts.seed [--username demo] [--password demopassword]
                      [--first Demo] [--last User] [--days 1095]

Re-running clears and regenerates that user's transactions, so it's safe to
run repeatedly while iterating on the demo.
"""
import argparse
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import zip_longest

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

import pandas as pd

import services.bond_pricing as bond_pricing
import services.market_data as market_data
from db.connection import get_engine, init_db
from db.models import (
    Asset, AssetTransaction, Bond, CashTransaction, LimitOrder, User, WatchlistEntry,
)
from services.asset_providers import PROVIDERS
from services.auth import normalize_username

# Spread across sectors rather than one basket of megacap tech, so the
# composition donut has visibly different slices and the performance line
# isn't just NASDAQ traced twice.
STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
    'JPM', 'V', 'JNJ', 'WMT', 'XOM', 'KO', 'DIS', 'COST',
]
CRYPTOS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD', 'ADA-USD', 'XRP-USD']
MARKET_TICKERS = {t: 'stock' for t in STOCKS} | {t: 'crypto' for t in CRYPTOS}
BOND_COUNT = 5

# Scaled with the ticker count: the same deposits split across three times
# as many names would leave every position too small to read.
INITIAL_DEPOSIT_RANGE = (80_000, 150_000)
EVENT_SPACING_DAYS = (2, 6)
DEPOSIT_RANGE = (1_000, 12_000)
WITHDRAW_RANGE = (200, 4_000)
BUY_DOLLAR_RANGE = (800, 9_000)
SELL_FRACTION_RANGE = (0.1, 0.6)
CASH_RESERVE = Decimal('2000')
EVENT_WEIGHTS = {'buy': 0.45, 'deposit': 0.30, 'sell': 0.15, 'withdraw': 0.10}

WATCHLIST_COUNT = 12
PENDING_ORDER_COUNT = 4
FILLED_ORDER_COUNT = 3
CANCELLED_ORDER_COUNT = 2
FAR_FROM_MARKET = Decimal('0.5')


def find_or_create_user(session, username, password, first_name, last_name):
    """
    The demo user, created if they don't exist yet.

    The username goes through the same normalisation services.auth applies,
    because that is the form login will look for. Inserting the raw string
    instead produced an account that could never be signed into: `--username
    Demo` stored "Demo", and logging in as either "Demo" or "demo" searched
    for "demo" and found nothing.
    """
    username = normalize_username(username)
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
    return user.userId, username


def pick_bonds(session, today):
    """
    Up to BOND_COUNT unmatured bonds from the catalog, as {ticker: dict}.

    Read through the model rather than through bond_pricing's own lookups,
    which use the Flask request-scoped session this script doesn't have -
    but serialised and judged with that module's public helpers, so a bond
    is priced here exactly as it is everywhere else.
    """
    bonds = session.scalars(select(Bond).order_by(Bond.maturityDate)).all()
    chosen = {}
    for bond in bonds:
        terms = bond_pricing.serialize_bond(bond)
        if bond_pricing.is_matured(terms, today):
            continue
        chosen[bond.ticker] = terms
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
    session.execute(delete(LimitOrder).where(LimitOrder.userId == user_id))
    session.execute(delete(WatchlistEntry).where(WatchlistEntry.userId == user_id))
    session.execute(delete(CashTransaction).where(CashTransaction.userId == user_id))
    session.execute(delete(AssetTransaction).where(AssetTransaction.userId == user_id))
    session.commit()


def pick_watchlist(asset_type_of, available, count):
    """
    Up to `count` tickers spread across the asset types, as {ticker: type}.

    Taken in turn from each type rather than off the front of the list,
    which is grouped: slicing it gave a watchlist of nothing but stocks,
    on an account whose whole point is showing three kinds of asset.
    """
    by_type = defaultdict(list)
    for ticker in available:
        by_type[asset_type_of[ticker]].append(ticker)

    interleaved = [
        ticker
        for group in zip_longest(*by_type.values())
        for ticker in group
        if ticker is not None
    ]
    return {ticker: asset_type_of[ticker] for ticker in interleaved[:count]}


def seed_watchlist(session, user_id, tickers, now):
    """
    Leave some tickers saved, so the dashboard opens on a real watchlist
    rather than on the "most active today" suggestions that stand in when
    nothing has been saved.

    addedAt is written explicitly and staggered, for the same reason
    services.watchlist writes it: the column's own default only has second
    resolution, and every row here would otherwise land in the same tick and
    order arbitrarily.
    """
    for offset, (ticker, asset_type) in enumerate(tickers.items()):
        session.add(WatchlistEntry(
            userId=user_id,
            ticker=ticker,
            assetType=asset_type,
            addedAt=now - timedelta(minutes=offset),
        ))
    session.commit()


def seed_orders(session, user_id, last_prices, now):
    """
    Several conditional orders in each status, so every tab of the orders
    view opens on a list rather than on a single row.

    The pending ones are placed far from the market on purpose - a demo
    account whose open orders fill as soon as the poller notices them would
    show an empty tab to anyone who looked a minute later. The filled ones
    are linked to real trades of the user's, which is what makes their
    realised gains line up with the transaction history.
    """
    tradable = [
        ticker for ticker, asset_type in MARKET_TICKERS.items()
        if ticker in last_prices and PROVIDERS[asset_type].supports_limit_orders
    ]
    if not tradable:
        return 0

    def far_from_market(ticker):
        return (last_prices[ticker] * FAR_FROM_MARKET).quantize(Decimal('0.01'))

    orders = []

    # Alternating, so the tab shows both order types and both directions.
    for offset, ticker in enumerate(tradable[:PENDING_ORDER_COUNT]):
        buying = offset % 2 == 0
        orders.append(LimitOrder(
            userId=user_id, ticker=ticker,
            side='buy' if buying else 'sell',
            orderType='limit' if buying else 'stop',
            quantity=Decimal('2') if buying else Decimal('1'),
            limitPrice=far_from_market(ticker),
            status='pending', createdAt=now - timedelta(days=offset + 1),
        ))

    filled_trades = session.scalars(
        select(AssetTransaction)
        .where(
            AssetTransaction.userId == user_id,
            AssetTransaction.ticker.in_(tradable),
            AssetTransaction.qty > 0,
        )
        .order_by(AssetTransaction.assetTransactionDate.desc())
        .limit(FILLED_ORDER_COUNT)
    ).all()

    for trade in filled_trades:
        orders.append(LimitOrder(
            userId=user_id, ticker=trade.ticker, side='buy', orderType='limit',
            quantity=trade.qty, limitPrice=trade.price, status='filled',
            createdAt=trade.assetTransactionDate - timedelta(days=1),
            resolvedAt=trade.assetTransactionDate,
            assetTransactionId=trade.assetTransactionId,
        ))

    for offset, ticker in enumerate(tradable[-CANCELLED_ORDER_COUNT:]):
        placed = now - timedelta(days=30 + offset)
        orders.append(LimitOrder(
            userId=user_id, ticker=ticker, side='buy', orderType='limit',
            quantity=Decimal('1'), limitPrice=far_from_market(ticker),
            status='cancelled',
            createdAt=placed, resolvedAt=placed + timedelta(days=1),
        ))

    session.add_all(orders)
    session.commit()
    return len(orders)


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

    user_id, username = find_or_create_user(session, username, password, first_name, last_name)

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

    watched = pick_watchlist(tickers, available_tickers, WATCHLIST_COUNT)
    seed_watchlist(session, user_id, watched, now)

    last_prices = {
        ticker: Decimal(str(round(float(series.iloc[-1]), 2)))
        for ticker, series in histories.items()
    }
    order_count = seed_orders(session, user_id, last_prices, now)
    session.close()

    print(f"Seeded user {first_name} {last_name} (userId={user_id}, login: {username} / {password})")
    print(f"  {len(cash_rows)} cash transactions, {len(asset_rows)} asset transactions")
    print(f"  {len(watched)} watchlist entries, {order_count} conditional orders")
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
    parser.add_argument('--days', type=int, default=1095)
    args = parser.parse_args()
    run(args.username, args.password, args.first, args.last, args.days)
