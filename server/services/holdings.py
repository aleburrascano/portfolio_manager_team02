"""
A user's open positions: what they hold, what it cost, and what it's worth
now.

The portfolio breakdown in asset_transactions answers "how much is in each
asset class"; this answers "which positions make that up", which is what a
holdings table and the sorting in issue #27 need.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from services.asset_providers import PROVIDERS
from services.portfolio_performance import average_cost_basis
from services.serialization import utc_iso
from services.user_transactions import get_user_asset_transactions

MARKET_TIMEZONE = ZoneInfo('America/New_York')


def _quote_book(held: Dict[str, str]) -> Dict[str, Tuple[float, float]]:
    """
    Current price and today's move for every held ticker, as
    {ticker: (price, change)}.

    Batched per asset type through the streaming quote path, so a book of
    twenty stocks costs one upstream call rather than twenty. An asset type
    that doesn't stream - a bond - falls back to its valuation price with
    no daily change, which is honest: a bond repriced from its own terms
    doesn't have an intraday move.
    """
    by_type: Dict[str, List[str]] = defaultdict(list)
    for ticker, asset_type in held.items():
        by_type[asset_type].append(ticker)

    book: Dict[str, Tuple[float, float]] = {}
    for asset_type, tickers in by_type.items():
        provider = PROVIDERS[asset_type]
        quotes = {}
        try:
            quotes = provider.live_quotes(tickers)
        except Exception:
            quotes = {}

        for ticker in tickers:
            quote = quotes.get(ticker) or {}
            price = quote.get('currentPrice')
            if price is None:
                price = provider.valuation_price(ticker)
            book[ticker] = (float(price or 0.0), float(quote.get('change') or 0.0))

    return book


def _session_date() -> date:
    """
    Today's date at the exchange, which is what "today" means in a day
    change - not the server's date and not the user's.
    """
    return datetime.now(MARKET_TIMEZONE).date()


def _exchange_date(value: Any) -> Any:
    """
    The exchange-local date a stored timestamp falls on, or None if it
    isn't a timestamp.

    Trade times are written by the database in UTC, so they have to be
    read back in the exchange's zone before their date is taken. A trade
    at 8pm in New York is already the small hours of the next day in UTC,
    and calling that tomorrow would place a purchase outside the very
    session it was made in - which is precisely the after-hours case this
    exists to get right.
    """
    if not isinstance(value, datetime):
        return None
    stamped = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return stamped.astimezone(MARKET_TIMEZONE).date()


def _bought_this_session(trades: List[dict], session_day: date) -> Dict[str, Tuple[Decimal, Decimal]]:
    """
    What was bought today, as {ticker: (quantity, average price paid)}.

    Sales are ignored: this answers what the user has *taken on* during
    the session, which is what can't be credited with a move that had
    already happened when they bought it.
    """
    quantities: Dict[str, Decimal] = defaultdict(Decimal)
    costs: Dict[str, Decimal] = defaultdict(Decimal)

    for trade in trades:
        quantity = Decimal(str(trade['qty']))
        if quantity <= 0 or _exchange_date(trade['transactionDate']) != session_day:
            continue
        ticker = trade['ticker']
        quantities[ticker] += quantity
        costs[ticker] += quantity * Decimal(str(trade['price']))

    return {
        ticker: (quantity, costs[ticker] / quantity)
        for ticker, quantity in quantities.items()
        if quantity > 0
    }


def get_holdings(user_id: int) -> Dict[str, Any]:
    """
    Every position the user currently holds, valued at the current price.

    Positions closed out to zero are left out - they belong in the
    transaction history, not in a list of what is held.

    Returned largest-first, which is the order a holdings table wants to
    open in. Re-sorting is the client's job: the rows are bounded by how
    many assets one person holds and every sortable field is already in
    this payload, so sorting here would mean a round trip - and a fresh
    valuation_price lookup per ticker - for data the caller already has.

    Args:
        user_id (int): The ID of the user.

    Returns:
        dict: {'holdings': list[dict], 'totals': dict}
    """
    trades = get_user_asset_transactions(user_id)
    if not trades:
        return {'holdings': [], 'totals': _totals(0, 0.0, 0.0, 0.0)}

    quantities: Dict[str, Decimal] = {}
    asset_type_of: Dict[str, str] = {}
    first_bought: Dict[str, str] = {}

    for trade in trades:
        ticker = trade['ticker']
        asset_type_of[ticker] = trade['assetType']
        quantities[ticker] = quantities.get(ticker, Decimal('0')) + Decimal(str(trade['qty']))
        if ticker not in first_bought and Decimal(str(trade['qty'])) > 0:
            first_bought[ticker] = _iso(trade['transactionDate'])

    cost_basis = average_cost_basis(trades)
    bought_today = _bought_this_session(trades, _session_date())

    held = {
        ticker: asset_type_of[ticker]
        for ticker, quantity in quantities.items()
        if quantity > 0
    }
    quotes = _quote_book(held)

    holdings = []
    raw_value = 0.0
    raw_cost = 0.0
    raw_day_change = 0.0

    for ticker, asset_type in held.items():
        quantity = quantities[ticker]
        unit_cost = float(cost_basis.get(ticker, Decimal('0')))
        price, change = quotes[ticker]
        value = float(quantity) * price
        cost = float(quantity) * unit_cost
        day_change = _day_change(quantity, price, change, bought_today.get(ticker))
        raw_value += value
        raw_cost += cost
        raw_day_change += day_change

        holdings.append({
            'ticker': ticker,
            'assetType': asset_type,
            'quantity': float(quantity),
            'currentPrice': round(price, 2),
            'averageCost': round(unit_cost, 2),
            'value': round(value, 2),
            'costBasis': round(cost, 2),
            'gainLoss': round(value - cost, 2),
            'gainLossPercent': round((value - cost) / cost * 100, 2) if cost else 0.0,
            'dayChange': round(day_change, 2),
            'acquiredAt': first_bought.get(ticker),
        })

    holdings.sort(key=lambda row: row['value'], reverse=True)
    return {
        'holdings': holdings,
        'totals': _totals(len(holdings), raw_value, raw_cost, raw_day_change),
    }


def _day_change(
    quantity: Decimal,
    price: float,
    change: float,
    bought_today: Tuple[Decimal, Decimal] = None,
) -> float:
    """
    What this position has actually made today, in currency.

    Shares held since before the session moved by `change`, which the feed
    measures from the previous close. Shares bought during it did not:
    they moved from what was paid for them. Crediting a purchase with the
    whole day's move is how buying a stock that had already risen 5% shows
    an instant 5% gain on money that was in cash while it happened.

    The split is by quantity rather than by lot because the cost basis
    above is an average too - a sale reduces the position without picking
    a lot, so there is no lot left to point at.
    """
    if not bought_today:
        return float(quantity) * change

    session_quantity, paid = bought_today
    session_quantity = min(session_quantity, quantity)
    prior_quantity = quantity - session_quantity

    return float(prior_quantity) * change + float(session_quantity) * (price - float(paid))


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return utc_iso(value)
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _totals(positions: int, value: float, cost: float, day_change: float = 0.0) -> dict:
    """The footer row: the whole book at market against what it cost."""
    opening = value - day_change
    return {
        'positions': positions,
        'value': round(value, 2),
        'costBasis': round(cost, 2),
        'gainLoss': round(value - cost, 2),
        'gainLossPercent': round((value - cost) / cost * 100, 2) if cost else 0.0,
        'dayChange': round(day_change, 2),
        'dayChangePercent': round(day_change / opening * 100, 2) if opening else 0.0,
    }
