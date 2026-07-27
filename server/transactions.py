from db import get_db

CASH_SIGN = {'deposit': 1, 'withdraw': -1}
STOCK_SIGN = {'buy': -1, 'sell': 1}

def get_user_transactions(user_id):
    conn = get_db()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT cashTransactionId as transactionId, transactionType, amount, "
        "cashTransactionDate as transactionDate FROM CashTransactions WHERE userId = %s",
        (user_id,)
    )
    cash_rows = cursor.fetchall()
    for row in cash_rows:
        row['type'] = 'cash'
        row['signedAmount'] = CASH_SIGN[row['transactionType']] * row['amount']

    cursor.execute(
        "SELECT stockTransactionId as transactionId, stockTransactionType as transactionType, "
        "amount, price, stockTransactionDate as transactionDate FROM StockTransactions WHERE userId = %s",
        (user_id,)
    )
    stock_rows = cursor.fetchall()
    for row in stock_rows:
        row['type'] = 'stock'
        row['signedAmount'] = STOCK_SIGN[row['transactionType']] * row['amount'] * row['price']

    cursor.close()

    transactions = cash_rows + stock_rows
    transactions.sort(key=lambda row: row['transactionDate'], reverse=True)
    return transactions

def get_user_balance(user_id):
    transactions = get_user_transactions(user_id)
    if transactions is None:
        return None
    return sum(row['signedAmount'] for row in transactions)
