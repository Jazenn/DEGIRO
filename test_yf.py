import yfinance as yf

tkrs1 = yf.Ticker("ASWC.DE")
print("ASWC.DE history:")
print(tkrs1.history(period="5d"))

tkrs2 = yf.Ticker("NATO.DE")
print("NATO.DE history:")
print(tkrs2.history(period="5d"))
