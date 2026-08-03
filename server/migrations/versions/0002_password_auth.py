"""add username and passwordHash to Users

Rows that predate password auth are backfilled with a username derived from
the name plus the userId (unique by construction) and an empty hash. An
empty hash never matches a candidate password, so those accounts stay
locked until a password is set for them - see scripts/set_password.py.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

users = sa.table(
    'Users',
    sa.column('userId', sa.Integer),
    sa.column('username', sa.String),
    sa.column('firstName', sa.String),
)


def upgrade() -> None:
    with op.batch_alter_table('Users') as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(32), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('passwordHash', sa.String(255), nullable=False, server_default=''))

    connection = op.get_bind()
    existing = connection.execute(
        sa.select(users.c.userId, users.c.firstName).where(users.c.username == '')
    ).all()
    for user_id, first_name in existing:
        connection.execute(
            users.update().where(users.c.userId == user_id)
            .values(username=f'{first_name.lower()}{user_id}')
        )

    with op.batch_alter_table('Users') as batch_op:
        batch_op.create_unique_constraint('uniqueUsername', ['username'])
        batch_op.alter_column('username', existing_type=sa.String(32),
                              existing_nullable=False, server_default=None)
        batch_op.alter_column('passwordHash', existing_type=sa.String(255),
                              existing_nullable=False, server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('Users') as batch_op:
        batch_op.drop_constraint('uniqueUsername', type_='unique')
        batch_op.drop_column('passwordHash')
        batch_op.drop_column('username')
