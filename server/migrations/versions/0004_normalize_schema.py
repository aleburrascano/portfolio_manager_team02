"""normalize schema and add supporting indexes

Four things, all on tables that already hold data:

- Extracts Assets(ticker, assetType) from AssetTransactions. assetType is a
  property of the ticker, not of the trade, and moving it out means adding a
  new kind of asset is an INSERT rather than an ALTER on an ENUM.
- Drops AssetTransactions.val, which was exactly -qty * price and had
  already drifted from it on 5 of 73 rows in production.
- Adds the indexes the user-scoped queries actually filter on, and CHECK
  constraints so each type column can't disagree with the sign beside it.
- Adds Users.createdAt, and lowercases existing usernames to match the
  normalisation services.auth now applies.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 8)

users = sa.table('Users', sa.column('username', sa.String))
asset_transactions = sa.table(
    'AssetTransactions', sa.column('ticker', sa.String), sa.column('assetType', sa.String)
)


def upgrade() -> None:
    connection = op.get_bind()

    op.create_table(
        'Assets',
        sa.Column('ticker', sa.String(12), nullable=False),
        sa.Column('assetType', sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint('ticker'),
    )
    connection.execute(
        sa.text(
            'INSERT INTO Assets (ticker, assetType) '
            'SELECT DISTINCT ticker, assetType FROM AssetTransactions'
        )
    )

    with op.batch_alter_table('AssetTransactions') as batch_op:
        batch_op.drop_column('val')
        batch_op.drop_column('assetType')
        batch_op.create_foreign_key(
            'fkAssetTransactionTicker', 'Assets', ['ticker'], ['ticker']
        )
        batch_op.create_check_constraint(
            'assetQtyMatchesType',
            "(assetTransactionType = 'buy' AND qty > 0)"
            " OR (assetTransactionType = 'sell' AND qty < 0)",
        )
        batch_op.create_check_constraint('assetPricePositive', 'price > 0')
        batch_op.create_index('ixAssetUserDate', ['userId', 'assetTransactionDate'])
        batch_op.create_index('ixAssetUserTicker', ['userId', 'ticker'])
        batch_op.create_index('ixAssetTicker', ['ticker'])

    with op.batch_alter_table('CashTransactions') as batch_op:
        batch_op.create_check_constraint(
            'cashAmountMatchesType',
            "(cashTransactionType = 'deposit' AND amount > 0)"
            " OR (cashTransactionType = 'withdraw' AND amount < 0)",
        )
        batch_op.create_index('ixCashUserDate', ['userId', 'cashTransactionDate'])

    with op.batch_alter_table('IdempotentRequests') as batch_op:
        batch_op.drop_column('statusCode')
        batch_op.create_index('ixIdempotentCreated', ['createdAt'])

    op.add_column(
        'Users',
        sa.Column('createdAt', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    connection.execute(users.update().values(username=sa.func.lower(users.c.username)))


def downgrade() -> None:
    connection = op.get_bind()

    op.drop_column('Users', 'createdAt')

    with op.batch_alter_table('IdempotentRequests') as batch_op:
        batch_op.drop_index('ixIdempotentCreated')
        batch_op.add_column(sa.Column('statusCode', sa.Integer(), nullable=True))

    with op.batch_alter_table('CashTransactions') as batch_op:
        batch_op.drop_index('ixCashUserDate')
        batch_op.drop_constraint('cashAmountMatchesType', type_='check')

    with op.batch_alter_table('AssetTransactions') as batch_op:
        batch_op.drop_index('ixAssetTicker')
        batch_op.drop_index('ixAssetUserTicker')
        batch_op.drop_index('ixAssetUserDate')
        batch_op.drop_constraint('assetPricePositive', type_='check')
        batch_op.drop_constraint('assetQtyMatchesType', type_='check')
        batch_op.drop_constraint('fkAssetTransactionTicker', type_='foreignkey')
        batch_op.add_column(
            sa.Column('assetType', sa.Enum('stock', 'crypto', name='assetType'), nullable=True)
        )
        batch_op.add_column(sa.Column('val', MONEY, nullable=True))

    connection.execute(
        sa.text(
            'UPDATE AssetTransactions SET assetType = '
            '(SELECT assetType FROM Assets WHERE Assets.ticker = AssetTransactions.ticker)'
        )
    )
    connection.execute(sa.text('UPDATE AssetTransactions SET val = -qty * price'))

    with op.batch_alter_table('AssetTransactions') as batch_op:
        batch_op.alter_column('assetType', existing_type=sa.String(16), nullable=False)
        batch_op.alter_column('val', existing_type=MONEY, nullable=False)

    op.drop_table('Assets')
