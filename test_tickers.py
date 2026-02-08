
import yfinance as yf
import pandas as pd

tickers = ["VWCE.DE", "VWCE.AS", "ASWC.DE"]
now = pd.Timestamp.now()

print(f"Testing tickers at {now}")
for t in tickers:
    try:
        data = yf.download(t, period="2d", interval="1h", progress=False)
        if not data.empty:
            last_price = data["Close"].iloc[-1]
            last_time = data.index[-1]
            print(f"{t}: Price {last_price:.4f}, Last Datapoint: {last_time}")
        else:
            print(f"{t}: EMPTY")
    except Exception as e:
        print(f"{t}: ERROR {e}")
