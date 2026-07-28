from flask import Flask, jsonify, request
import mysql.connector
import yfinance as yf

app = Flask(__name__)

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="portfolio_manager",
)
mycursor = mydb.cursor()


def user_transaction_history(user_id):
    connection = mydb
    mycursor.execute("SELECT cashTransactionId AS id, transactionType AS type, amount, cashTransactionDate AS timestamp, 'cash' AS category"
                   "FROM CashTransactions WHERE userId = %s",(user_id,)
                )
    users_cash_transactions = mycursor.fetchall()

    mycursor.execute(
        "SELECT stockTransactionId AS id, transactionType AS type, quantity, stockTransactionDate AS timestamp, 'stock' AS category, ticker, price FROM StockTransactions WHERE userId = %s",
        (user_id,)
    )
    users_stock_transactions = mycursor.fetchall()

    mycursor.close()
    connection.close()

    combined = users_cash_transactions + users_stock_transactions
    combined.sort(key=lambda item: item["timestamp"])

    return jsonify({"transactions": combined})


@app.route('/transactions/<int:user_id>')
def transactions_route(user_id):
    return user_transaction_history(user_id)


@app.route('/stock/<ticker>')
def stock_route(ticker):
    return jsonify(stock_info(ticker))


def stock_info(ticker):
    day_history = yf.Ticker(ticker).history(period="1d")
    year_history = yf.Ticker(ticker).history(period="1y")

    return {
        "symbol": ticker.upper(),
        "day_high": float(day_history["High"].values[0]),
        "day_low": float(day_history["Low"].values[0]),
        "day_open": float(day_history["Open"].values[0]),
        "day_volume": int(day_history["Volume"].values[0]),
        "day_close": float(day_history["Close"].values[0]),
        "year_high": float(year_history["High"].max()),
        "year_low": float(year_history["Low"].min()),
    }


def _stock_history(ticker):
    history = yf.Ticker(ticker).history(period="1y")
    return history["Close"]


if __name__ == '__main__':
    app.run(debug=True)