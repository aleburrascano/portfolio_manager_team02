"""
SQLAlchemy models mirroring db/schema/schema.sql.

Column names stay camelCase to match the existing schema (and the JSON the
client already reads), rather than renaming the database to suit Python
conventions.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Money and quantities are DECIMAL(18,8) so balance/holdings math is exact.
MONEY = Numeric(18, 8)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'Users'

    userId: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # The login identity. First/last name are display-only, and deliberately
    # not unique - two people are allowed to share a name.
    username: Mapped[str] = mapped_column(String(32), unique=True)
    firstName: Mapped[str] = mapped_column(String(32))
    lastName: Mapped[str] = mapped_column(String(32))
    # Werkzeug PBKDF2 digest, never the password itself.
    passwordHash: Mapped[str] = mapped_column(String(255))


class CashTransaction(Base):
    __tablename__ = 'CashTransactions'

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
    __tablename__ = 'AssetTransactions'

    assetTransactionId: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assetType: Mapped[str] = mapped_column(Enum('stock', 'crypto', name='assetType'))
    ticker: Mapped[str] = mapped_column(String(12))
    qty: Mapped[Decimal] = mapped_column(MONEY)
    price: Mapped[Decimal] = mapped_column(MONEY)
    val: Mapped[Decimal] = mapped_column(MONEY)
    assetTransactionType: Mapped[str] = mapped_column(
        Enum('buy', 'sell', name='assetTransactionType')
    )
    assetTransactionDate: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    userId: Mapped[int] = mapped_column(ForeignKey('Users.userId', ondelete='CASCADE'))
