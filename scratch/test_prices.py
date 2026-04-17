import yfinance as yf
import pandas as pd

def check_btc():
    ticker = "BTC-EUR"
    data = yf.download(ticker, period="1y")
    if data.empty:
        print("No data found")
        return
    
    # In newer yfinance versions, it's a multi-index if we use download
    # Better use Ticker object for precision
    t = yf.Ticker(ticker)
    h = t.history(period="1y")
    
    if h.empty:
        print("Ticker history empty")
        return
        
    y_max = h["High"].max()
    y_min = h["Low"].min()
    
    print(f"Ticker: {ticker}")
    print(f"Max: {y_max}")
    print(f"Min: {y_min}")
    print(f"Current Row Count: {len(h)}")
    print(f"Start Date: {h.index.min()}")
    print(f"End Date: {h.index.max()}")

if __name__ == "__main__":
    check_btc()
