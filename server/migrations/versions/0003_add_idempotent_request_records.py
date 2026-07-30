"""add idempotent request records

Backs Idempotency-Key support on the money-moving routes. The composite
primary key is what makes claiming a key atomic: concurrent duplicates
collide on it, so exactly one request does the work.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'IdempotentRequests',
        sa.Column('userId', sa.Integer(), nullable=False),
        sa.Column('idempotencyKey', sa.String(64), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('statusCode', sa.Integer(), nullable=True),
        sa.Column('responseBody', sa.Text(), nullable=True),
        sa.Column('createdAt', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['userId'], ['Users.userId'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('userId', 'idempotencyKey'),
    )


def downgrade() -> None:
    op.drop_table('IdempotentRequests')
