"""
Place, cancel, list, and fill GTC limit orders for stocks.

Placing and cancelling are request-scoped, exactly like buy/sell. Filling
is different: it isn't triggered by a request at all, it's driven by
evaluate_pending_orders(), which limit_order_poller calls on a timer from
its own DB session. Keeping that function here (not in the poller module)
is what makes it directly unit-testable the same way purchase_asset/
sell_asset already are - construct an app context, call it, assert on the
database - with the sleep loop itself as a thin, separately tested wrapper.
"""
import collections
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select

import db.connection as db_conn
import services.market_data as market_data
import services.user_transactions as ut
from db.models import Asset, LimitOrder
from services.asset_providers import PROVIDERS
from services.asset_transactions import get_holding_qty_decimal, record_trade, register_asset
from services.exceptions import (
    InsufficientFunds, InsufficientHoldings, InvalidInput, MarketDataUnavailable,
    OrderNotFound, UnknownUser,
)

SIDES = ('buy', 'sell')
ORDER_TYPES = ('limit', 'stop')

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_limit_order_support(asset_type: str) -> None:
    if not PROVIDERS[asset_type].supports_limit_orders:
        raise InvalidInput('Limit orders are only supported for stocks right now.')


def place_limit_order(
    user_id: int, asset_type: str, ticker: str, side: str, quantity: Decimal,
    limit_price: Decimal, order_type: str = 'limit',
) -> LimitOrder:
    """
    Queue a GTC conditional order, either a limit or a stop.

    A quick, point-in-time affordability check runs now under the user row
    lock - the same check purchase_asset/sell_asset make - so an order that
    obviously can't be covered is rejected immediately, the same experience
    as a market order. It is NOT a reservation: nothing is escrowed, so it
    is re-checked for real at fill time (evaluate_pending_orders), because
    the user's balance or holdings can legitimately move between now and
    then.

    A limit buy can never fill above limit_price, so that is exactly what
    the cash check needs. A stop buy triggers on the way *up* and fills at
    whatever the market is then, which is a cost with no ceiling - there is
    no honest figure to check it against, so the check uses the trigger
    price as the nearest thing and the real one still happens at fill time.

    Raises:
        UnknownUser: no such user.
        InvalidInput: the asset type doesn't take conditional orders, side
            isn't buy/sell, order_type isn't limit/stop, or (for a buy) the
            asset can't currently be bought.
        MarketDataUnavailable: the asset can't be priced (from registering
            a never-before-traded ticker).
        InsufficientFunds / InsufficientHoldings: as of right now, the
            order couldn't be covered if it filled immediately.
    """
    if side not in SIDES:
        raise InvalidInput("side must be 'buy' or 'sell'.")
    if order_type not in ORDER_TYPES:
        raise InvalidInput("orderType must be 'limit' or 'stop'.")
    _require_limit_order_support(asset_type)

    provider = PROVIDERS[asset_type]
    session = db_conn.get_session()
    try:
        if side == 'buy':
            tradable, reason = provider.can_trade(ticker)
            if not tradable:
                raise InvalidInput(reason or 'This asset cannot be bought.')

        if not db_conn.lock_user(session, user_id):
            raise UnknownUser('No such user.')

        register_asset(session, provider, ticker)

        if side == 'buy':
            if ut.get_user_balance(user_id) < quantity * limit_price:
                raise InsufficientFunds('Not enough cash to cover this order if it fills right now.')
        else:
            if get_holding_qty_decimal(user_id, ticker) < quantity:
                raise InsufficientHoldings('Not enough shares to cover this order if it fills right now.')

        order = LimitOrder(
            userId=user_id, ticker=ticker, side=side, orderType=order_type,
            quantity=quantity, limitPrice=limit_price, status='pending',
        )
        session.add(order)
        session.commit()
        return order
    except Exception:
        session.rollback()
        raise


def _lock_order(session, limit_order_id: int) -> Optional[LimitOrder]:
    """
    Row-lock one order by ID, the same SQLite-skipping way db_conn.lock_user
    locks a user - so a cancel and a poller fill of the same order can't
    both act on it: whichever gets here first wins, and the other sees the
    resolved status and no-ops (the poller) or reports it (cancel).
    """
    statement = select(LimitOrder).where(LimitOrder.limitOrderId == limit_order_id)
    if session.get_bind().dialect.name != 'sqlite':
        statement = statement.with_for_update()
    return session.scalar(statement)


def cancel_limit_order(user_id: int, limit_order_id: int) -> None:
    """
    Cancel a pending order. Safe to call twice: the second call finds the
    order already resolved and raises rather than double-cancelling, so a
    client retry after a dropped response can't do anything harmful.

    Raises:
        OrderNotFound: no such order, or it belongs to another user.
        InvalidInput: the order isn't pending any more (filled/cancelled).
    """
    session = db_conn.get_session()
    try:
        order = _lock_order(session, limit_order_id)
        if order is None or order.userId != user_id:
            raise OrderNotFound('No such order.')
        if order.status != 'pending':
            raise InvalidInput('This order is no longer pending.')

        order.status = 'cancelled'
        order.resolvedAt = _now()
        session.commit()
    except Exception:
        session.rollback()
        raise


def list_limit_orders(
    user_id: int, asset_type: Optional[str] = None, status: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[LimitOrder]:
    """
    A user's conditional orders, newest first, optionally filtered by asset
    type and status.

    The asset type is a real filter rather than only a route segment: now
    that more than one type takes conditional orders, a caller asking for a
    stock's orders would otherwise be handed the crypto ones too. It comes
    from the Assets row, which is the one place a ticker's type is recorded.

    A pending list stays short - orders leave it as they fill or are
    cancelled - but filled and cancelled ones accumulate for as long as the
    account is used, so a caller showing history can ask for a page of it.
    """
    statement = select(LimitOrder).where(LimitOrder.userId == user_id)
    if asset_type is not None:
        statement = statement.join(Asset, Asset.ticker == LimitOrder.ticker).where(
            Asset.assetType == asset_type
        )
    if status is not None:
        statement = statement.where(LimitOrder.status == status)
    statement = statement.order_by(LimitOrder.createdAt.desc(), LimitOrder.limitOrderId.desc())
    if limit is not None:
        statement = statement.limit(limit)
    return db_conn.get_session().scalars(statement).all()


def evaluate_pending_orders() -> int:
    """
    Fill every pending order whose condition is met right now, at the
    market price prevailing at the moment of the fill (not the price that
    was true when the condition was first noticed) - all-or-nothing, one
    AssetTransaction per fill.

    Prices are found in two stages. One batched quote call screens every
    pending ticker at once: a ticker no waiting order could fill at - which
    on any given tick is nearly all of them - is dropped there and costs
    nothing further. Only the tickers that look like they have crossed are
    then priced individually through trade_price, the same call a market
    order books at, so a fill still executes at the authoritative price
    rather than at the indicative one used to screen it.

    Each candidate is then locked and resolved independently: a user (or
    order) row lock means one fill can't race a manual trade, a manual
    cancel, or another fill for the same user, but a stuck or slow fill for
    one user never blocks another user's.

    If a buy's cost (or a sell's quantity) can no longer be covered at fill
    time - the user spent the cash or sold the shares elsewhere since
    placing the order - the order is left pending rather than cancelled.
    There is no reservation system, so "temporarily can't afford it" and
    "will never be able to afford it" look identical from here; the safer
    default for a GTC order is to keep trying rather than to guess.

    Returns:
        list[dict]: one row per fill, describing what happened. Returned
        rather than announced: a fill is worth telling its owner about, but
        this module has no Flask and no socket, so the caller (the poller)
        does the telling.
    """
    session = db_conn.get_session()
    pending = session.scalars(
        select(LimitOrder).where(LimitOrder.status == 'pending')
        .order_by(LimitOrder.createdAt, LimitOrder.limitOrderId)
    ).all()
    if not pending:
        return []

    by_ticker = collections.defaultdict(list)
    for order in pending:
        by_ticker[order.ticker].append(order)

    screen = _indicative_prices(list(by_ticker))

    filled = []
    for ticker, orders in by_ticker.items():
        indicative = screen.get(ticker)
        if indicative is not None and not any(_condition_met(order, indicative) for order in orders):
            continue

        try:
            price = market_data.trade_price(ticker)
        except MarketDataUnavailable:
            continue

        for order in orders:
            fill = _try_fill(session, order.limitOrderId, price)
            if fill is not None:
                filled.append(fill)
    return filled


def _indicative_prices(tickers: List[str]) -> dict:
    """
    One batched quote call for every pending ticker, as {ticker: Decimal}.

    Only used to decide which tickers are worth pricing properly, so a
    failure here is not worth reporting - it just means nothing gets
    screened out and every ticker is priced the slow way, exactly as before.
    """
    try:
        quotes = market_data.live_quotes(tickers)
    except Exception:
        return {}

    prices = {}
    for ticker, quote in quotes.items():
        price = quote.get('currentPrice')
        if price is not None:
            prices[ticker] = Decimal(str(price))
    return prices


def _condition_met(order: LimitOrder, price: Decimal) -> bool:
    """
    Whether `price` has crossed this order's trigger.

    A limit order waits for a price at least as good as its trigger; a stop
    order waits for one at least as bad. That single reversal is the whole
    difference between the two, which is why both live in one table and one
    poller rather than two of each.
    """
    waits_for_a_fall = (order.side == 'buy') == (order.orderType == 'limit')
    return price <= order.limitPrice if waits_for_a_fall else price >= order.limitPrice


def _try_fill(session, limit_order_id: int, price: Decimal) -> Optional[dict]:
    """
    Fill one order under its own lock, if its condition still holds.

    Returns a description of the fill, or None if it didn't happen. Read
    into a plain dict before returning, because the caller reports it after
    this session is gone and a detached ORM row would not survive the trip.
    """
    try:
        order = _lock_order(session, limit_order_id)
        if order is None or order.status != 'pending':
            return None

        if not _condition_met(order, price):
            return None

        if not db_conn.lock_user(session, order.userId):
            return None

        if order.side == 'buy':
            if ut.get_user_balance(order.userId) < order.quantity * price:
                return None
        else:
            if get_holding_qty_decimal(order.userId, order.ticker) < order.quantity:
                return None

        tx = record_trade(session, order.userId, order.ticker, order.quantity, price, order.side)
        order.status = 'filled'
        order.assetTransactionId = tx.assetTransactionId
        order.resolvedAt = _now()

        fill = {
            'userId': order.userId,
            'limitOrderId': order.limitOrderId,
            'ticker': order.ticker,
            'side': order.side,
            'orderType': order.orderType,
            'quantity': float(order.quantity),
            'price': float(price),
            'assetTransactionId': tx.assetTransactionId,
        }
        session.commit()
        return fill
    except Exception:
        logger.exception('Limit order %s failed to fill', limit_order_id)
        session.rollback()
        return None
