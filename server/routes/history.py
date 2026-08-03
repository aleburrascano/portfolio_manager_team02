import csv
import io
from typing import Tuple

from flask import Response

from services.portfolio_performance import realized_gains_for
from services.user_transactions import count_user_transactions, get_user_transactions
from apidocs import Blueprint
from authorization import require_user
from links import transactions_links
from schemas import TransactionsQuerySchema

history_bp = Blueprint('history', __name__, description='Transaction history')

MAX_PAGE_SIZE = 500

CSV_COLUMNS = (
    'Date', 'Type', 'Action', 'Ticker', 'Quantity', 'Price', 'Amount',
    'Cost basis', 'Realized gain/loss',
)


def _with_realized(rows: list, realized: dict) -> list:
    """
    Hang each sale's realised gain off the row it belongs to.

    Only sales get one - a buy realises nothing and a deposit isn't a trade
    - so the field is absent rather than zero on every other row, which is
    the difference between "made nothing" and "not that kind of event".
    """
    for row in rows:
        gain = realized.get(row['transactionId']) if row['type'] != 'cash' else None
        if gain is not None:
            row['realized'] = gain
    return rows

@history_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
@require_user
@history_bp.arguments(TransactionsQuerySchema, location='query')
def get_transaction_history(query: dict, user_id: int) -> Tuple[dict, int]:
    """
    Get a user's chronological transaction history (cash and asset).

    `total` is the count before paging, so a caller asking for one page can
    tell whether there is another without fetching it.

    A sell also carries a `realized` block saying what that sale actually
    made against the average cost of the position it came out of.

    Returns:
        dict: {'userId': int, 'transactions': list[dict], 'total': int,
        '_links': dict}
    """
    limit = query.get('limit')
    if limit is not None:
        limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, query.get('offset') or 0)
    newest_first = query.get('sort') != 'oldest'

    rows = get_user_transactions(user_id, limit, offset, newest_first)
    return {
        'userId': user_id,
        'transactions': _with_realized(rows, realized_gains_for(user_id)),
        'total': count_user_transactions(user_id),
        '_links': transactions_links(user_id),
    }, 200


def _csv_cell(value):
    """
    One cell, with formula injection defused.

    A ticker is upstream data and a spreadsheet treats a leading =, +, - or
    @ as the start of a formula, so a downloaded file could execute what a
    feed put in a name. Prefixing with an apostrophe is what keeps this a
    record of trades rather than a delivery mechanism.
    """
    if value is None:
        return ''
    text = str(value)
    return f"'{text}" if text[:1] in ('=', '+', '-', '@') else text


@history_bp.route('/users/<int:user_id>/transactions/export', methods=['GET'])
@require_user
def export_transaction_history(user_id: int) -> Response:
    """
    Download the whole history as CSV.

    Deliberately unpaged: the point of an export is to get everything in one
    file, and it is one query against the same index the paged view uses.

    Returns:
        Response: text/csv as a download.
    """
    rows = _with_realized(get_user_transactions(user_id), realized_gains_for(user_id))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        realized = row.get('realized') or {}
        writer.writerow([
            _csv_cell(row['transactionDate']),
            _csv_cell(row['type']),
            _csv_cell(row['transactionType']),
            _csv_cell(row['ticker']),
            _csv_cell(row['qty']),
            _csv_cell(row['price']),
            _csv_cell(row['signedAmount']),
            _csv_cell(realized.get('costBasis')),
            _csv_cell(realized.get('gainLoss')),
        ])

    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=transactions.csv'},
    )
