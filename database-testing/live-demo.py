import mysql.connector
import yfinance as yf

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="<PASSWORD>",
    database="portfolio_manager"
)
mycursor = mydb.cursor()


def addUserUnique(firstName, lastName) -> int:
    # Check if the user already exists in the database
    query = "SELECT * FROM users WHERE firstName = %s AND lastName = %s"
    mycursor.execute(query, (firstName, lastName))
    result = mycursor.fetchone()

    # Insert new user into the database
    if not result:
        sql = "INSERT INTO users (firstName, lastName) VALUES (%s, %s)"
        val = (firstName, lastName)
        mycursor.execute(sql, val)
        mydb.commit()

        # Retrieve new user ID
        mycursor.execute(query, (firstName, lastName))
        result = mycursor.fetchone()

    return int(result[0])  # Return the user ID


def purchaseStock(user_id, ticker, quantity):
    # Get current price from yfinance
    stock = yf.Ticker(ticker)
    current_price = stock.history(period="1d")['Close'].iloc[0]

    # Insert purchase into the stockTransactions table
    sql = "INSERT INTO stockTransactions (ticker, amount, price, stockTransactionType, userId) VALUES (%s, %s, %s, %s, %s)"
    val = (ticker, quantity, current_price, "buy", user_id)
    mycursor.execute(sql, val)

    mydb.commit()


user_id = addUserUnique("Sang", "Shin")
purchaseStock(user_id, "AAPL", 10)
mydb.close()
