import yfinance as yf

result = yf.screen("most_actives")

for quote in result["quotes"]:
    print(quote["symbol"], quote["regularMarketVolume"])
