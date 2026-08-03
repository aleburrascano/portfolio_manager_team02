"""add stop orders

A stop order is a limit order with its trigger comparison reversed: a limit
buy waits for the price to fall to limitPrice, a stop buy waits for it to
rise to it, and the same mirrored for a sell. One column carries which of
the two an order is; everything else about placing, cancelling, listing and
filling them is already shared.

Existing rows are all limit orders, which is what the server default says,
so the column can be added NOT NULL without a backfill pass.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'LimitOrders',
        sa.Column(
            'orderType',
            sa.Enum('limit', 'stop', name='limitOrderType'),
            server_default='limit',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('LimitOrders', 'orderType')
