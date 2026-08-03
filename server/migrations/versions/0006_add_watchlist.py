"""add the per-user watchlist

A ticker a user has saved to follow, whether or not they hold any of it.

There is deliberately no foreign key to Assets: that table records what has
been transacted, and the point of a watchlist is to follow something before
buying it. The asset type is carried on the row instead, so the right
provider can be asked for a price.

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'WatchlistEntries',
        sa.Column('userId', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=12), nullable=False),
        sa.Column('assetType', sa.String(length=16), nullable=False),
        sa.Column('addedAt', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['userId'], ['Users.userId'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('userId', 'ticker'),
    )
    op.create_index('ixWatchlistUserAdded', 'WatchlistEntries', ['userId', 'addedAt'])


def downgrade() -> None:
    op.drop_index('ixWatchlistUserAdded', table_name='WatchlistEntries')
    op.drop_table('WatchlistEntries')
