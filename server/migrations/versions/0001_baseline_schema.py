"""baseline schema

The schema as it stood before Alembic was adopted: what db/schema/schema.sql
plus migrate_decimal_precision.sql produced. Databases created that way
should be stamped at this revision rather than upgraded to it:

    alembic stamp 0001

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 8)


def upgrade() -> None:
    op.create_table(
        'Users',
        sa.Column('userId', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('firstName', sa.String(32), nullable=False),
        sa.Column('lastName', sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint('userId'),
    )

    op.create_table(
        'CashTransactions',
        sa.Column('cashTransactionId', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cashTransactionType', sa.Enum('deposit', 'withdraw', name='cashTransactionType'), nullable=False),
        sa.Column('amount', MONEY, nullable=False),
        sa.Column('cashTransactionDate', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('userId', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['userId'], ['Users.userId'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('cashTransactionId'),
    )

    op.create_table(
        'AssetTransactions',
        sa.Column('assetTransactionId', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assetType', sa.Enum('stock', 'crypto', name='assetType'), nullable=False),
        sa.Column('ticker', sa.String(12), nullable=False),
        sa.Column('qty', MONEY, nullable=False),
        sa.Column('price', MONEY, nullable=False),
        sa.Column('val', MONEY, nullable=False),
        sa.Column('assetTransactionType', sa.Enum('buy', 'sell', name='assetTransactionType'), nullable=False),
        sa.Column('assetTransactionDate', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('userId', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['userId'], ['Users.userId'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('assetTransactionId'),
    )


def downgrade() -> None:
    op.drop_table('AssetTransactions')
    op.drop_table('CashTransactions')
    op.drop_table('Users')
