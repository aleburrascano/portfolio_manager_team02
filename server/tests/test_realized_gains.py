"""
What a sale actually made.

Pure arithmetic over a trade ledger, so these call the function directly
with rows in the shape get_user_asset_transactions returns - no database
and no market data involved.
"""
from services.portfolio_performance import realized_gains


def trade(transaction_id, ticker, qty, price):
    """One row in the shape the ledger hands back; qty is signed."""
    return {'transactionId': transaction_id, 'ticker': ticker, 'qty': qty, 'price': price}


def test_a_buy_realises_nothing():
    assert realized_gains([trade(1, 'AAPL', 10, 10)]) == {}


def test_a_sale_at_a_profit():
    gains = realized_gains([trade(1, 'AAPL', 10, 10), trade(2, 'AAPL', -4, 15)])

    assert gains[2] == {
        'costBasis': 40.0, 'proceeds': 60.0, 'gainLoss': 20.0, 'gainLossPercent': 50.0,
    }


def test_a_sale_at_a_loss():
    gains = realized_gains([trade(1, 'AAPL', 10, 10), trade(2, 'AAPL', -10, 8)])

    assert gains[2]['gainLoss'] == -20.0
    assert gains[2]['gainLossPercent'] == -20.0


def test_a_sale_uses_the_average_at_the_time():
    gains = realized_gains([
        trade(1, 'AAPL', 10, 10),
        trade(2, 'AAPL', -5, 12),
        trade(3, 'AAPL', 10, 20),
        trade(4, 'AAPL', -5, 20),
    ])

    assert gains[2]['costBasis'] == 50.0
    assert gains[4]['costBasis'] == round(5 * (5 * 10 + 10 * 20) / 15, 2)


def test_closing_out_then_buying_back_in_resets_the_basis():
    gains = realized_gains([
        trade(1, 'AAPL', 10, 10),
        trade(2, 'AAPL', -10, 12),
        trade(3, 'AAPL', 10, 30),
        trade(4, 'AAPL', -10, 33),
    ])

    assert gains[2]['costBasis'] == 100.0
    assert gains[4]['costBasis'] == 300.0


def test_tickers_are_kept_apart():
    gains = realized_gains([
        trade(1, 'AAPL', 10, 10),
        trade(2, 'MSFT', 10, 50),
        trade(3, 'AAPL', -10, 11),
    ])

    assert gains[3]['costBasis'] == 100.0
    assert set(gains) == {3}


def test_a_sale_of_something_never_bought_reports_no_cost():
    """
    Not reachable through the API - selling is checked against holdings -
    but the arithmetic must not divide by zero if a ledger ever says it.
    """
    gains = realized_gains([trade(1, 'AAPL', -5, 10)])

    assert gains[1]['costBasis'] == 0.0
    assert gains[1]['gainLossPercent'] == 0.0


def test_every_sale_is_reported():
    gains = realized_gains([
        trade(1, 'AAPL', 10, 10),
        trade(2, 'AAPL', -2, 11),
        trade(3, 'AAPL', -2, 12),
    ])

    assert sorted(gains) == [2, 3]
