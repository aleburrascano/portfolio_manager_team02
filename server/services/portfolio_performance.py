"""
A user's portfolio value over time, and how it compares to the money they
put in.

Replays the trade and cash ledgers forward day by day, valuing whatever was
held on each date at that day's closing price. Prices come from each asset
type's provider, so bonds - which no feed quotes - are valued from the same
catalog that prices them everywhere else.

Deliberately no pandas, numpy or matplotlib here: the work is a running
total over a few hundred dates, plain Python does it without adding three
dependencies to a web request, and a plotting library has no business
inside a request handler at all.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from services.asset_providers import PROVIDERS
from services.user_transactions import get_cash_flows, get_user_asset_transactions

# Where the comparison starts before the user picks something else: the
# S&P 500 tracker. Only a default - any asset the catalog can price is a
# legal benchmark, so "what if I had just bought Bitcoin instead" is as
# answerable here as "did I beat the index".
BENCHMARK_ASSET_TYPE = 'stock'
BENCHMARK_TICKER = 'SPY'


def _as_date(value: Any) -> date:
    """Normalise a datetime, date or ISO string to a plain date."""
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value.date() if hasattr(value, 'date') else value


def _today() -> date:
    """
    Today in the same frame the ledger is stamped in, which is UTC.

    Not date.today(): that is the server's local date, and the dates it
    would be compared against here come from transaction timestamps the
    database writes in UTC. Anywhere west of Greenwich the two disagree
    for the last hours of the day - a deposit made at 8pm in New York is
    already tomorrow in UTC, so it sorts after a local "today", the replay
    loop below never reaches it, and the chart comes back empty for a
    portfolio that plainly has something in it.
    """
    return datetime.now(timezone.utc).date()


def _close_by_date(asset_type: str, ticker: str, days: int) -> Dict[date, float]:
    """
    A {date: close} map for one ticker, or an empty map if it has no history.

    `days` is the chart window, passed through so the closes fetched actually
    span it: a five-year chart valued against a single year of history left
    every older holding at zero for the years it couldn't see.

    Best-effort on purpose: one ticker whose history can't be fetched should
    leave a gap in the chart, not fail the whole request.
    """
    provider = PROVIDERS.get(asset_type)
    if provider is None:
        return {}

    try:
        history = provider.get_history(ticker, days)
    except Exception:
        return {}

    return {
        _as_date(point['date']): float(point['close'])
        for point in history
        if point.get('close') is not None
    }


def get_portfolio_performance(
    user_id: int,
    days: int = 365,
    benchmark_type: str = BENCHMARK_ASSET_TYPE,
    benchmark_ticker: str = BENCHMARK_TICKER,
) -> Dict[str, Any]:
    """
    Chart a user's portfolio value over the last `days` days.

    Each point carries the whole picture for that date: the assets at market
    value, the cash alongside them, the two combined, and the net deposits
    they were bought with. Gain/loss is the difference between the last two,
    which is the only comparison that means anything - a portfolio that grew
    because the user paid more in has not performed.

    Args:
        user_id (int): The ID of the user.
        days (int): How far back to chart.
        benchmark_type (str): The asset type the benchmark is priced by.
        benchmark_ticker (str): What to measure the portfolio against.

    Each point also carries `benchmarkValue`: what the same deposits, made
    on the same days, would be worth in that benchmark instead. "Did I
    beat my own deposits" is the weaker of the two comparisons available
    here, and it was the only one being offered.

    Returns:
        dict: {'series': list[dict], 'summary': dict, 'byAssetType':
        list[dict], 'benchmark': dict}
    """
    benchmark = {'assetType': benchmark_type, 'ticker': benchmark_ticker}
    trades = get_user_asset_transactions(user_id)
    cash_flows = get_cash_flows(user_id)

    if not trades and not cash_flows:
        return {
            'series': [], 'summary': _empty_summary(), 'byAssetType': [],
            'benchmark': benchmark,
        }

    today = _today()
    first_activity = min(_as_date(row['transactionDate']) for row in trades + cash_flows)
    start = max(first_activity, today - timedelta(days=days))

    asset_type_of = {row['ticker']: row['assetType'] for row in trades}
    closes = {
        ticker: _close_by_date(asset_type, ticker, days)
        for ticker, asset_type in asset_type_of.items()
    }

    trades_on: Dict[date, List[dict]] = defaultdict(list)
    for row in trades:
        trades_on[_as_date(row['transactionDate'])].append(row)

    cash_on: Dict[date, Decimal] = defaultdict(Decimal)
    for row in cash_flows:
        cash_on[_as_date(row['transactionDate'])] += Decimal(str(row['amount']))

    shares: Dict[str, Decimal] = defaultdict(Decimal)
    last_price: Dict[str, Optional[float]] = {ticker: None for ticker in asset_type_of}
    traded_price: Dict[str, float] = {}
    cash = Decimal('0')
    net_deposits = Decimal('0')
    series: List[dict] = []

    day = first_activity
    while day <= today:
        for trade in trades_on.get(day, ()):
            quantity = Decimal(str(trade['qty']))
            shares[trade['ticker']] += quantity
            cash -= quantity * Decimal(str(trade['price']))
            traded_price[trade['ticker']] = float(trade['price'])

        flow = cash_on.get(day)
        if flow:
            cash += flow
            net_deposits += flow

        for ticker, ticker_closes in closes.items():
            price = ticker_closes.get(day)
            if price is not None:
                last_price[ticker] = price

        if day >= start:
            # The most recent close, carried forward across market closures.
            # Before the first close a held ticker has - the day it was
            # bought, or a genuine hole at the left edge of the fetched
            # history - fall back to what it was traded at rather than zero,
            # so a position never blinks out to nothing on the day it appears.
            invested = sum(
                float(quantity) * (last_price.get(ticker) or traded_price.get(ticker) or 0.0)
                for ticker, quantity in shares.items()
                if quantity
            )
            series.append({
                'date': day.isoformat(),
                'investedValue': round(invested, 2),
                'cash': round(float(cash), 2),
                'portfolioValue': round(invested + float(cash), 2),
                'netDeposits': round(float(net_deposits), 2),
            })

        day += timedelta(days=1)

    held = {ticker: qty for ticker, qty in shares.items() if qty}
    still_held_by_type: Dict[str, List[str]] = defaultdict(list)
    for ticker in held:
        still_held_by_type[asset_type_of[ticker]].append(ticker)

    live_price: Dict[str, float] = {}
    for asset_type, tickers in still_held_by_type.items():
        live_price.update(PROVIDERS[asset_type].valuation_prices(tickers))

    for ticker, price in live_price.items():
        if not price:
            live_price[ticker] = last_price.get(ticker) or traded_price.get(ticker) or 0.0

    if series:
        invested = sum(float(qty) * live_price[ticker] for ticker, qty in held.items())
        latest = series[-1]
        latest['investedValue'] = round(invested, 2)
        latest['portfolioValue'] = round(invested + latest['cash'], 2)

    comparison = _benchmark_series(series, benchmark_type, benchmark_ticker, days)
    for point, valued in zip(series, comparison):
        point['benchmarkValue'] = valued['benchmarkValue']

    return {
        'series': series,
        'summary': _summarise(series),
        'byAssetType': _by_asset_type(shares, asset_type_of, live_price, trades),
        'benchmark': benchmark,
    }


def _benchmark_series(
    series: List[dict], asset_type: str, ticker: str, days: int,
) -> List[dict]:
    """
    What the same money would have been worth in `ticker` instead, on the
    same dates.

    Priced through the same provider registry the holdings are, rather than
    off the market feed directly, so anything the app can sell can also be
    compared against - a bond the catalog prices as readily as an index
    fund the feed quotes.

    Deposits are matched, not just the opening balance: a portfolio that was
    topped up halfway through would otherwise be compared against a
    benchmark that never received the money, which flatters it for no reason
    other than timing. Every dollar goes in on the day it arrived and buys
    that day's close.

    Best-effort like everything else on this chart: if the benchmark can't
    be priced, the comparison is simply absent rather than the whole request
    failing.
    """
    if not series:
        return []

    closes = _close_by_date(asset_type, ticker, days)
    if not closes:
        return []

    units = 0.0
    last_close = None
    pending = 0.0
    previous_deposits = 0.0
    benchmark = []

    for point in series:
        close = closes.get(_as_date(point['date'])) or last_close
        if close:
            last_close = close

        # A dollar that arrives before the index has a price to buy at is
        # held over, not dropped: it goes in at the first close available
        # rather than never - the same failure the holdings replay had, where
        # a contribution on an unpriced day silently vanished from the
        # comparison and flattered whichever side it landed on.
        pending += point['netDeposits'] - previous_deposits
        previous_deposits = point['netDeposits']
        if close and pending:
            units += pending / close
            pending = 0.0

        benchmark.append({
            'date': point['date'],
            'benchmarkValue': round(units * close, 2) if close else 0.0,
        })

    return benchmark


def _empty_summary() -> dict:
    return {
        'startValue': 0.0,
        'currentValue': 0.0,
        'netDeposits': 0.0,
        'gainLoss': 0.0,
        'gainLossPercent': 0.0,
    }


def _summarise(series: List[dict]) -> dict:
    """Headline numbers for the chart: where it ended up against what went in."""
    if not series:
        return _empty_summary()

    latest = series[-1]
    net_deposits = latest['netDeposits']
    gain_loss = latest['portfolioValue'] - net_deposits

    return {
        'startValue': series[0]['portfolioValue'],
        'currentValue': latest['portfolioValue'],
        'netDeposits': net_deposits,
        'gainLoss': round(gain_loss, 2),
        'gainLossPercent': round(gain_loss / net_deposits * 100, 2) if net_deposits else 0.0,
    }


def _by_asset_type(
    shares: Dict[str, Decimal],
    asset_type_of: Dict[str, str],
    price_of: Dict[str, Optional[float]],
    trades: List[dict],
) -> List[dict]:
    """
    Gain/loss per asset class, measured against what was paid for what is
    still held, so positions already sold don't distort it.

    Priced at the same live valuation the final series point uses, so the
    class breakdown adds up to the headline above it.
    """
    cost_basis = average_cost_basis(trades)

    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: {'value': 0.0, 'cost': 0.0})
    for ticker, quantity in shares.items():
        if not quantity:
            continue
        bucket = totals[asset_type_of[ticker]]
        bucket['value'] += float(quantity) * (price_of.get(ticker) or 0.0)
        bucket['cost'] += float(quantity) * float(cost_basis.get(ticker, Decimal('0')))

    return [
        {
            'assetType': asset_type,
            'value': round(bucket['value'], 2),
            'costBasis': round(bucket['cost'], 2),
            'gainLoss': round(bucket['value'] - bucket['cost'], 2),
            'gainLossPercent': (
                round((bucket['value'] - bucket['cost']) / bucket['cost'] * 100, 2)
                if bucket['cost'] else 0.0
            ),
        }
        for asset_type, bucket in sorted(totals.items())
    ]


def realized_gains_for(user_id: int) -> Dict[int, Dict[str, float]]:
    """
    Every sale this user has made and what it realised, keyed by the
    transactionId of the sale.

    Needs the whole trade ledger regardless of what the caller is showing:
    an average cost basis is built by replaying every buy that came before a
    sale, so it can't be computed from one page of history.
    """
    return realized_gains(get_user_asset_transactions(user_id))


def realized_gains(trades: List[dict]) -> Dict[int, Dict[str, float]]:
    """
    What each sale actually made, keyed by its transactionId.

    The unrealised side of this is fully built - holdings reports gain
    against average cost for every open position - but a closed one left no
    trace: a sale showed up in the history as a signed amount and nothing
    said whether it was a good one.

    Measured against the same average cost basis the open positions use, so
    "sold at a gain" here and "up on the position" there mean the same thing
    and are computed one way. Replayed forward with the cost basis rather
    than read off the finished one, because the average moves as a position
    is added to and a sale has to be judged against the average as it stood
    at the time.

    Only sales appear; a buy realises nothing.

    Args:
        trades (list[dict]): Asset trades, oldest first, with signed `qty`
            and a `transactionId`.

    Returns:
        dict[int, dict]: {'costBasis', 'proceeds', 'gainLoss',
        'gainLossPercent'} per sale.
    """
    quantities: Dict[str, Decimal] = defaultdict(Decimal)
    averages: Dict[str, Decimal] = defaultdict(Decimal)
    realized: Dict[int, Dict[str, float]] = {}

    for trade in trades:
        ticker = trade['ticker']
        quantity = Decimal(str(trade['qty']))
        price = Decimal(str(trade['price']))
        held = quantities[ticker]

        if quantity > 0:
            total_cost = averages[ticker] * held + quantity * price
            quantities[ticker] = held + quantity
            averages[ticker] = total_cost / quantities[ticker]
            continue

        sold = -quantity
        unit_cost = averages[ticker]
        cost = sold * unit_cost
        proceeds = sold * price

        transaction_id = trade.get('transactionId')
        if transaction_id is not None:
            realized[transaction_id] = {
                'costBasis': round(float(cost), 2),
                'proceeds': round(float(proceeds), 2),
                'gainLoss': round(float(proceeds - cost), 2),
                'gainLossPercent': round(float((proceeds - cost) / cost * 100), 2) if cost else 0.0,
            }

        quantities[ticker] = held + quantity
        if quantities[ticker] <= 0:
            quantities[ticker] = Decimal('0')
            averages[ticker] = Decimal('0')

    return realized


def average_cost_basis(trades: List[dict]) -> Dict[str, Decimal]:
    """
    The average price paid per unit still held, per ticker.

    A sale reduces the position without moving the average, which is the
    conventional treatment and keeps the basis stable as a position is
    trimmed. A position closed out to zero resets, so buying back in starts
    from the new price rather than inheriting an old one.

    Args:
        trades (list[dict]): Asset trades, oldest first, with signed `qty`.

    Returns:
        dict[str, Decimal]: Average unit cost, keyed by ticker.
    """
    quantities: Dict[str, Decimal] = defaultdict(Decimal)
    averages: Dict[str, Decimal] = defaultdict(Decimal)

    for trade in trades:
        ticker = trade['ticker']
        quantity = Decimal(str(trade['qty']))
        price = Decimal(str(trade['price']))
        held = quantities[ticker]

        if quantity > 0:
            total_cost = averages[ticker] * held + quantity * price
            quantities[ticker] = held + quantity
            averages[ticker] = total_cost / quantities[ticker]
        else:
            quantities[ticker] = held + quantity
            if quantities[ticker] <= 0:
                quantities[ticker] = Decimal('0')
                averages[ticker] = Decimal('0')

    return averages
