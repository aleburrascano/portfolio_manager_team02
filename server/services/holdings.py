"""
A user's open positions: what they hold, what it cost, and what it's worth
now.

The portfolio breakdown in asset_transactions answers "how much is in each
asset class"; this answers "which positions make that up", which is what a
holdings table and the sorting in issue #27 need.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from services.asset_providers import PROVIDERS
from services.portfolio_performance import average_cost_basis
from services.user_transactions import get_user_asset_transactions


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
                # Best-effort by design: one unpriceable ticker should leave
                # a zero in the table rather than fail the whole request.
                price = provider.valuation_price(ticker)
            book[ticker] = (float(price or 0.0), float(quote.get('change') or 0.0))

    return book


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
        # Trades arrive oldest first, so the first buy seen is the date the
        # position was opened - what "sort by date acquired" means.
        if ticker not in first_bought and Decimal(str(trade['qty'])) > 0:
            first_bought[ticker] = _iso(trade['transactionDate'])

    cost_basis = average_cost_basis(trades)

    held = {
        ticker: asset_type_of[ticker]
        for ticker, quantity in quantities.items()
        if quantity > 0
    }
    quotes = _quote_book(held)

    holdings = []
    # Accumulated unrounded, because rounding each position and then summing
    # drifts a cent or two away from the same book totalled anywhere else -
    # and the performance headline sits directly above this table.
    raw_value = 0.0
    raw_cost = 0.0
    raw_day_change = 0.0

    for ticker, asset_type in held.items():
        quantity = quantities[ticker]
        unit_cost = float(cost_basis.get(ticker, Decimal('0')))
        price, change = quotes[ticker]
        value = float(quantity) * price
        cost = float(quantity) * unit_cost
        day_change = float(quantity) * change
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


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _totals(positions: int, value: float, cost: float, day_change: float = 0.0) -> dict:
    """The footer row: the whole book at market against what it cost."""
    # Yesterday's close of the same book, which is what today's move is a
    # move from - so the percentage is against that, not against today.
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
