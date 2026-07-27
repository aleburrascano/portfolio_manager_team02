import yfinance as yf

ticker = "MS"
data = yf.download(ticker, start="2026-07-01", end="2026-07-20")

print(f"\n{ticker} Historical Data:")
print(data.head())
print(f"\nData shape: {data.shape}")

ticker_info = yf.Ticker(ticker)
print(f"\n{ticker} Info:")
print(f"Name: {ticker_info.info.get('longName', 'N/A')}")
print(f"Current Price: ${ticker_info.info.get('currentPrice', 'N/A')}")
