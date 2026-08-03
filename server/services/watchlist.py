"""
The tickers a user has saved to follow.

Distinct from holdings: a watchlist is what you are considering, not what
you own, so nothing here touches transactions. Entries are quoted through
the same providers everything else uses, so a saved bond is priced from the
catalog and a saved stock from the market feed without this module knowing
the difference.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import delete, select

from db.connection import get_session
from db.models import WatchlistEntry
from services.asset_providers import PROVIDERS
from services.exceptions import InvalidInput

# A watchlist is something a person reads at a glance; past this it is a
# database query with extra steps, and it would cost a quote lookup each.
MAX_ENTRIES = 24


def _now() -> datetime:
    """
    Naive UTC, matching every other DateTime this schema writes.

    Written from Python rather than left to the column's server default:
    SQLite's CURRENT_TIMESTAMP only has second resolution, so two tickers
    saved in the same second would carry identical timestamps and "newest
    first" would come down to whatever order the rows happened to come back
    in. There is no autoincrement column here to break the tie with - the
    primary key is (userId, ticker) - so the timestamp has to carry the
    ordering itself.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalise(ticker: str) -> str:
    if not isinstance(ticker, str) or not ticker.strip():
        raise InvalidInput('ticker is required.')
    return ticker.strip().upper()


def is_watched(user_id: int, ticker: str) -> bool:
    """Whether this user has saved this ticker."""
    return get_session().get(WatchlistEntry, (user_id, _normalise(ticker))) is not None


def add(user_id: int, asset_type: str, ticker: str) -> None:
    """
    Save a ticker to the user's watchlist.

    Idempotent: saving something already saved leaves the original entry
    (and its addedAt) alone rather than moving it to the top of the list.

    Raises:
        InvalidInput: on an unknown asset type, a blank ticker, or a list
        that is already full.
    """
    if asset_type not in PROVIDERS:
        raise InvalidInput(f'{asset_type} is not a supported asset type.')

    ticker = _normalise(ticker)
    session = get_session()

    if session.get(WatchlistEntry, (user_id, ticker)) is not None:
        return

    watched = session.scalar(
        select(WatchlistEntry).where(WatchlistEntry.userId == user_id).limit(MAX_ENTRIES).offset(MAX_ENTRIES - 1)
    )
    if watched is not None:
        raise InvalidInput(
            f'Your watchlist is full ({MAX_ENTRIES} assets). Remove one to save another.'
        )

    session.add(
        WatchlistEntry(userId=user_id, ticker=ticker, assetType=asset_type, addedAt=_now())
    )
    session.commit()


def remove(user_id: int, ticker: str) -> None:
    """Drop a ticker from the watchlist. Removing what isn't there is fine."""
    session = get_session()
    session.execute(
        delete(WatchlistEntry).where(
            WatchlistEntry.userId == user_id,
            WatchlistEntry.ticker == _normalise(ticker),
        )
    )
    session.commit()


def list_entries(user_id: int) -> List[Dict[str, Any]]:
    """
    The saved tickers, newest first, each with a current quote.

    Quotes are batched per asset type, so a list of twenty stocks is one
    upstream call rather than twenty. A ticker that can't be quoted still
    comes back carrying its symbol - a row with a dash reads better than a
    silently missing one.
    """
    # ticker breaks ties within the same addedAt tick (SQLite's
    # CURRENT_TIMESTAMP only has second resolution), so two tickers saved in
    # the same second don't reorder between renders.
    entries = get_session().scalars(
        select(WatchlistEntry)
        .where(WatchlistEntry.userId == user_id)
        .order_by(WatchlistEntry.addedAt.desc(), WatchlistEntry.ticker.asc())
    ).all()

    if not entries:
        return []

    by_type: Dict[str, List[str]] = {}
    for entry in entries:
        by_type.setdefault(entry.assetType, []).append(entry.ticker)

    quotes: Dict[str, dict] = {}
    for asset_type, tickers in by_type.items():
        provider = PROVIDERS.get(asset_type)
        if provider is None:
            continue
        for ticker in tickers:
            try:
                quote = provider.get_quote(ticker)
            except Exception:
                quote = None
            if quote:
                quotes[ticker] = quote

    return [
        {
            'symbol': entry.ticker,
            'assetType': entry.assetType,
            'addedAt': entry.addedAt.isoformat() if entry.addedAt else None,
            **{
                key: quotes.get(entry.ticker, {}).get(key)
                for key in ('name', 'currentPrice', 'change', 'changePercent')
            },
        }
        for entry in entries
    ]
