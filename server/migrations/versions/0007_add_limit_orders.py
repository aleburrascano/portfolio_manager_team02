"""add limit orders

Good-till-cancelled conditional buy/sell orders for stocks, filled by a
background poller (services.limit_orders.evaluate_pending_orders) once the
market price crosses the limit.

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 8)


def upgrade() -> None:
    op.create_table(
        'LimitOrders',
        sa.Column('limitOrderId', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('userId', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=12), nullable=False),
        sa.Column('side', sa.Enum('buy', 'sell', name='limitOrderSide'), nullable=False),
        sa.Column('quantity', MONEY, nullable=False),
        sa.Column('limitPrice', MONEY, nullable=False),
        sa.Column(
            'status',
            sa.Enum('pending', 'filled', 'cancelled', name='limitOrderStatus'),
            server_default='pending', nullable=False,
        ),
        sa.Column('createdAt', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolvedAt', sa.DateTime(), nullable=True),
        sa.Column('assetTransactionId', sa.Integer(), nullable=True),
        sa.CheckConstraint('quantity > 0', name='limitOrderQuantityPositive'),
        sa.CheckConstraint('limitPrice > 0', name='limitOrderPricePositive'),
        sa.ForeignKeyConstraint(['userId'], ['Users.userId'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticker'], ['Assets.ticker']),
        sa.ForeignKeyConstraint(['assetTransactionId'], ['AssetTransactions.assetTransactionId']),
        sa.PrimaryKeyConstraint('limitOrderId'),
    )
    op.create_index('ixLimitOrderStatusTicker', 'LimitOrders', ['status', 'ticker'])
    op.create_index('ixLimitOrderUserStatus', 'LimitOrders', ['userId', 'status', 'createdAt'])
    op.create_index('ixLimitOrderTicker', 'LimitOrders', ['ticker'])


def downgrade() -> None:
    op.drop_index('ixLimitOrderTicker', table_name='LimitOrders')
    op.drop_index('ixLimitOrderUserStatus', table_name='LimitOrders')
    op.drop_index('ixLimitOrderStatusTicker', table_name='LimitOrders')
    op.drop_table('LimitOrders')
