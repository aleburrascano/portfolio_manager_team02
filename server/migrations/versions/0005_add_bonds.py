"""add the bond catalog

Bonds aren't quoted by any market feed, so instead of a ticker symbol to
look up they carry the terms they're priced from - see
services.bond_pricing.

Each bond also gets an Assets row, because that's what lets a bond be
transacted like any other asset and what the trade foreign key points at.
Note the assetType enum did not have to grow to accommodate this: since
migration 0004 the type is a row in Assets rather than a column value.

Revision ID: 0005
Revises: 0004
"""
from datetime import date

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

CATALOG = [
    ('UST2Y', 'US Treasury Note 2Y', 1000, 0.0422, 0.0422, 'semiannual', '2026-07-15', '2028-07-15'),
    ('UST5Y', 'US Treasury Note 5Y', 1000, 0.0437, 0.0437, 'semiannual', '2026-07-15', '2031-07-15'),
    ('UST10Y', 'US Treasury Note 10Y', 1000, 0.0467, 0.0467, 'semiannual', '2026-07-15', '2036-07-15'),
    ('UST20Y', 'US Treasury Bond 20Y', 1000, 0.0521, 0.0521, 'semiannual', '2026-07-15', '2046-07-15'),
    ('AAPL2045', 'Apple Inc 3.450% 2045', 1000, 0.0345, 0.0566, 'semiannual', '2015-02-09', '2045-02-09'),
    ('MSFT2030', 'Microsoft Corp 1.350% 2030', 1000, 0.0135, 0.0421, 'semiannual', '2020-09-15', '2030-09-15'),
    ('JNJ2033', 'Johnson & Johnson 4.375% 2033', 1000, 0.0438, 0.0454, 'semiannual', '2023-12-05', '2033-12-05'),
    ('WMT2028', 'Walmart Inc 3.700% 2028', 1000, 0.0370, 0.0396, 'semiannual', '2018-06-26', '2028-06-26'),
    ('NYCGO27', 'NYC GO Bonds Fiscal 2017 Ser A', 1000, 0.0500, 0.0487, 'semiannual', '2016-08-01', '2027-08-01'),
    ('CAGO28', 'California GO Refunding Bond', 1000, 0.0300, 0.0290, 'semiannual', '2018-11-01', '2028-11-01'),
    ('CAGO34', 'California GO Bond 7.5% 2034', 1000, 0.0750, 0.0370, 'semiannual', '2004-04-01', '2034-04-01'),
]

assets = sa.table('Assets', sa.column('ticker', sa.String), sa.column('assetType', sa.String))
bonds = sa.table(
    'Bonds',
    sa.column('ticker', sa.String), sa.column('name', sa.String),
    sa.column('faceValue', sa.Numeric), sa.column('couponRate', sa.Numeric),
    sa.column('marketYield', sa.Numeric), sa.column('couponFrequency', sa.String),
    sa.column('issueDate', sa.Date), sa.column('maturityDate', sa.Date),
)


def upgrade() -> None:
    op.create_table(
        'Bonds',
        sa.Column('ticker', sa.String(12), nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('faceValue', sa.Numeric(18, 8), nullable=False),
        sa.Column('couponRate', sa.Numeric(6, 4), nullable=False),
        sa.Column('marketYield', sa.Numeric(6, 4), nullable=False),
        sa.Column(
            'couponFrequency',
            sa.Enum('annual', 'semiannual', name='couponFrequency'),
            server_default='semiannual',
            nullable=False,
        ),
        sa.Column('issueDate', sa.Date(), nullable=False),
        sa.Column('maturityDate', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['Assets.ticker']),
        sa.PrimaryKeyConstraint('ticker'),
    )

    connection = op.get_bind()
    connection.execute(
        assets.insert(),
        [{'ticker': row[0], 'assetType': 'bond'} for row in CATALOG],
    )
    connection.execute(
        bonds.insert(),
        [
            {
                'ticker': ticker, 'name': name, 'faceValue': face, 'couponRate': coupon,
                'marketYield': yield_, 'couponFrequency': frequency,
                'issueDate': date.fromisoformat(issued),
                'maturityDate': date.fromisoformat(matures),
            }
            for ticker, name, face, coupon, yield_, frequency, issued, matures in CATALOG
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    tickers = [row[0] for row in CATALOG]
    op.drop_table('Bonds')
    connection.execute(assets.delete().where(assets.c.ticker.in_(tickers)))
