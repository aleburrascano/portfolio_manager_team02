"""
The database schema. Alembic migrations are generated from this file, so
it is the one place the shape of the data is defined.

Column names stay camelCase to match the original schema (and the JSON the
client already reads), rather than renaming the database to suit Python
conventions.

Two conventions worth knowing:

- Every timestamp is UTC. db.connection pins the session timezone so the
  database's own `now()` agrees with what Python writes.
- Transaction rows are append-only. Nothing updates or deletes them, which
  is why none of them carry an `updatedAt`.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Money and quantities are DECIMAL(18,8) so balance/holdings math is exact.
MONEY = Numeric(18, 8)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'Users'

    userId: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # The login identity, stored lowercased by services.auth so uniqueness
    # means the same thing on MySQL (case-insensitive collation) as it does
    # on SQLite (byte-exact). First/last name are display-only and
    # deliberately not unique - two people are allowed to share a name.
    username: Mapped[str] = mapped_column(String(32), unique=True)
    firstName: Mapped[str] = mapped_column(String(32))
    lastName: Mapped[str] = mapped_column(String(32))
    # Werkzeug PBKDF2 digest, never the password itself.
    passwordHash: Mapped[str] = mapped_column(String(255))
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IdempotentRequest(Base):
    """
    One row per Idempotency-Key a user has spent on a money-moving request.

    The composite primary key both scopes keys to their own user and gives
    the uniqueness constraint that makes claiming a key atomic: two
    concurrent requests race to insert, and exactly one wins.
    """

    __tablename__ = 'IdempotentRequests'
    # Indexed so the retention sweep in idempotency.py is a range scan
    # rather than a table scan.
    __table_args__ = (Index('ixIdempotentCreated', 'createdAt'),)

    userId: Mapped[int] = mapped_column(
        ForeignKey('Users.userId', ondelete='CASCADE'), primary_key=True
    )
    idempotencyKey: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Hash of the request the key was claimed for, so reusing a key for a
    # different request is caught instead of silently replaying the old one.
    fingerprint: Mapped[str] = mapped_column(String(64))
    # Null until the request succeeds; a null response means "in progress".
    # Only successful responses are stored, so there's no status to record
    # alongside it - a stored body always means 200.
    responseBody: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Asset(Base):
    """
    The tradable assets that have been transacted, and what kind each is.

    assetType lives here rather than on every transaction row because it's a
    property of the ticker, not of the trade - which also means adding a new
    kind of asset is an INSERT rather than an ALTER on an ENUM.
    """

    __tablename__ = 'Assets'

    ticker: Mapped[str] = mapped_column(String(12), primary_key=True)
    # Validated against the provider registry in services.asset_providers.
    assetType: Mapped[str] = mapped_column(String(16))


class Bond(Base):
    """
    The synthetic bond catalog: the terms each bond is priced from.

    Bonds aren't quoted by any market feed, so unlike a stock or a crypto
    their price is derived from these terms and the date - see
    services.bond_pricing. The ticker is also an Assets row, so a bond can
    be transacted like any other asset.
    """

    __tablename__ = 'Bonds'

    ticker: Mapped[str] = mapped_column(ForeignKey('Assets.ticker'), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    faceValue: Mapped[Decimal] = mapped_column(MONEY)
    # Rates are fractions, not percentages: 0.0422 is 4.22%.
    couponRate: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    marketYield: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    couponFrequency: Mapped[str] = mapped_column(
        Enum('annual', 'semiannual', name='couponFrequency'), server_default='semiannual'
    )
    issueDate: Mapped[date] = mapped_column(Date)
    maturityDate: Mapped[date] = mapped_column(Date)


class WatchlistEntry(Base):
    """
    A ticker a user has saved to watch, whether or not they hold any of it.

    Deliberately not a foreign key to Assets: that table records what has
    been *transacted*, and the whole point of a watchlist is to follow
    something before buying it. The asset type is carried here instead, so
    the right provider can be asked for a price.

    The composite primary key is also the uniqueness constraint - saving a
    ticker twice is the same row, so the toggle is idempotent for free.
    """

    __tablename__ = 'WatchlistEntries'
    __table_args__ = (Index('ixWatchlistUserAdded', 'userId', 'addedAt'),)

    userId: Mapped[int] = mapped_column(
        ForeignKey('Users.userId', ondelete='CASCADE'), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(12), primary_key=True)
    assetType: Mapped[str] = mapped_column(String(16))
    addedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CashTransaction(Base):
    __tablename__ = 'CashTransactions'
    __table_args__ = (
        # The type and the sign of the amount say the same thing; this stops
        # them from ever disagreeing.
        CheckConstraint(
            "(cashTransactionType = 'deposit' AND amount > 0)"
            " OR (cashTransactionType = 'withdraw' AND amount < 0)",
            name='cashAmountMatchesType',
        ),
        Index('ixCashUserDate', 'userId', 'cashTransactionDate'),
    )

    cashTransactionId: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cashTransactionType: Mapped[str] = mapped_column(
        Enum('deposit', 'withdraw', name='cashTransactionType')
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    cashTransactionDate: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    userId: Mapped[int] = mapped_column(ForeignKey('Users.userId', ondelete='CASCADE'))


class AssetTransaction(Base):
    """
    One buy or sell. The cash effect is -qty * price and is computed where
    it's needed rather than stored, so it can't drift from the quantity and
    price it comes from.
    """

    __tablename__ = 'AssetTransactions'
    __table_args__ = (
        CheckConstraint(
            "(assetTransactionType = 'buy' AND qty > 0)"
            " OR (assetTransactionType = 'sell' AND qty < 0)",
            name='assetQtyMatchesType',
        ),
        CheckConstraint('price > 0', name='assetPricePositive'),
        Index('ixAssetUserDate', 'userId', 'assetTransactionDate'),
        # Serves the holdings lookup, which filters on both columns.
        Index('ixAssetUserTicker', 'userId', 'ticker'),
        # ticker leading, which is what InnoDB needs to back the foreign key
        # - the composite above has it second, so it doesn't qualify.
        Index('ixAssetTicker', 'ticker'),
    )

    assetTransactionId: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(ForeignKey('Assets.ticker'))
    qty: Mapped[Decimal] = mapped_column(MONEY)
    price: Mapped[Decimal] = mapped_column(MONEY)
    assetTransactionType: Mapped[str] = mapped_column(
        Enum('buy', 'sell', name='assetTransactionType')
    )
    assetTransactionDate: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    userId: Mapped[int] = mapped_column(ForeignKey('Users.userId', ondelete='CASCADE'))


class LimitOrder(Base):
    """
    A good-till-cancelled conditional buy or sell of a stock: fills at the
    current market price the first time it crosses limitPrice, or sits
    pending until it does or the user cancels it.

    Unlike AssetTransaction this row is mutable - status moves from
    'pending' to exactly one of 'filled'/'cancelled' - which is why, unlike
    AssetTransaction, it carries a resolvedAt. assetTransactionId is set
    only on a fill, linking the order to the one AssetTransaction row it
    produced.
    """

    __tablename__ = 'LimitOrders'
    __table_args__ = (
        CheckConstraint('quantity > 0', name='limitOrderQuantityPositive'),
        CheckConstraint('limitPrice > 0', name='limitOrderPricePositive'),
        # The poller's hot path: every pending order, grouped by ticker.
        Index('ixLimitOrderStatusTicker', 'status', 'ticker'),
        # A user's own orders, newest first (the Open Orders view).
        Index('ixLimitOrderUserStatus', 'userId', 'status', 'createdAt'),
        # ticker leading, which is what InnoDB needs to back the foreign
        # key - mirrors ixAssetTicker on AssetTransaction.
        Index('ixLimitOrderTicker', 'ticker'),
    )

    limitOrderId: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(ForeignKey('Users.userId', ondelete='CASCADE'))
    ticker: Mapped[str] = mapped_column(ForeignKey('Assets.ticker'))
    side: Mapped[str] = mapped_column(Enum('buy', 'sell', name='limitOrderSide'))
    quantity: Mapped[Decimal] = mapped_column(MONEY)
    limitPrice: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(
        Enum('pending', 'filled', 'cancelled', name='limitOrderStatus'),
        server_default='pending',
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolvedAt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assetTransactionId: Mapped[Optional[int]] = mapped_column(
        ForeignKey('AssetTransactions.assetTransactionId'), nullable=True
    )
