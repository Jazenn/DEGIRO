import pandas as pd
import yfinance as yf

def test_crypto_baseline():
    tickers = ["BTC-EUR", "ETH-EUR"]
    data = yf.download(" ".join(tickers), period="2d", interval="1h", group_by="ticker", prepost=True, progress=False, threads=True)
    
    for t in tickers:
        print(f"\n--- {t} ---")
        df_t = data[t].dropna(subset=["Close"]) if t in data else data.dropna(subset=["Close"])
        
        if not df_t.empty:
            hist = df_t.reset_index()
            col_dt = hist.columns[0]
            
            # Print raw UTC times
            print("Raw YF Hourly timestamps (UTC) and Closes for the last 36 hours:")
            print(hist[[col_dt, "Close"]].tail(36))
            
            if hist[col_dt].dt.tz is None:
                 hist[col_dt] = hist[col_dt].dt.tz_localize("UTC")
                 
            hist[col_dt] = hist[col_dt].dt.tz_convert("Europe/Amsterdam")
            
            # Print Local times
            print("\nLocalized Amsterdam Hourly timestamps and Closes:")
            print(hist[[col_dt, "Close"]].tail(36))
            
            today = pd.Timestamp.now(tz="Europe/Amsterdam").normalize()
            mask = hist[col_dt].dt.normalize() == today
            
            print(f"\nMidnight selection for {today.strftime('%Y-%m-%d')}:")
            if mask.any():
                 print(hist.loc[mask, [col_dt, "Close"]].head(2))
            else:
                 print("No midnight candle found!")

if __name__ == '__main__':
    test_crypto_baseline()
