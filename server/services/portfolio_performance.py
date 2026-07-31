import numpy as np
import pandas as pd
import yfinance as yf
from services.user_transactions import get_user_asset_transactions
"""
    Returns a DataFrame whose rows are trading dates and whose columns are
    tickers. Each value is the number of shares owned at the end of that day.


    Parameters
    ----------
    transactions : DataFrame
        Must contain:
            transactionDate
            ticker
            transactionType ("BUY" or "SELL")
            shares


    trading_dates : DatetimeIndex
        Usually the index from the downloaded yfinance price DataFrame.


    Returns
    -------
    DataFrame
        Daily holdings for every ticker.
    """




def daily_holdings(transactions, trading_dates):
    transactions = transactions.copy()
    transactions["transactionDate"] = pd.to_datetime(transactions["transactionDate"]).dt.normalize()
    transactions["qty"] = transactions["qty"].astype(float)
        # BUY = positive, SELL = negative
    transactions["signedShares"] = np.where(
        transactions["transactionType"] == "buy",
        transactions["qty"],
        -transactions["qty"]
    )

        # Daily changes in shares
    daily_changes = (
        transactions
        .groupby(["transactionDate", "ticker"])["signedShares"]
        .sum()
        .unstack(fill_value=0)
    )
   # Add every trading day
    daily_changes = daily_changes.reindex(
        trading_dates,
        fill_value=0
    )


    # Running total = shares owned
    holdings = daily_changes.cumsum()


    return holdings

 #extracting holdings
def get_portfolio_performance(user_id):
    asset_transactions = pd.DataFrame(get_user_asset_transactions(user_id))
    tickers = asset_transactions["ticker"].unique()
    asset_transactions["transactionDate"] = pd.to_datetime(asset_transactions["transactionDate"])
    start_date = asset_transactions["transactionDate"].min()
    end_date = pd.Timestamp.today().normalize()
    price_data = {}

    for ticker in tickers:
        price_data[ticker] = (
        yf.Ticker(ticker).history(start = start_date, end = end_date, auto_adjust=True)["Close"]
        )
    prices = pd.DataFrame(price_data)
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    holdings = daily_holdings(
        asset_transactions, prices.index
    )
    holdings = holdings.reindex(prices.index, fill_value=0)
    prices = prices.ffill()
    asset_values = holdings*prices
    portfolio_value = asset_values.sum(axis=1)
    performance = pd.DataFrame({ "date": portfolio_value.index, "portfolioValue": portfolio_value.values })
    performance["date"] = performance["date"].dt.strftime("%Y-%m-%d")
    import matplotlib.pyplot as plt
    plt.plot(performance["date"], performance["portfolioValue"])
    plt.show()
    return performance.to_dict(orient="records")


''' if __name__ == "__main__":
    import sys
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    records = get_portfolio_performance(user_id)
    debug_df = pd.DataFrame(records)

    plt.figure(figsize=(12, 5))
    plt.plot(pd.to_datetime(debug_df["date"]), debug_df["portfolioValue"], linewidth=2)
    plt.title("Portfolio Performance")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value")
    plt.grid(True)
    plt.tight_layout()

    out_path = f"portfolio_{user_id}.png"
    plt.savefig(out_path)
    print(f"Saved chart to {out_path}")













 '''