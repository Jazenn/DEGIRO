import yfinance as yf
import pandas as pd

def verify_fix():
    print("Fetching data for VWCE.DE...")
    # Fetch 5 years of data
    start_date = (pd.Timestamp.now() - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    
    try:
        data = yf.download(["VWCE.DE"], start=start_date, interval="1d", group_by="ticker", progress=False)
        
        if data.empty:
            print("FAILURE: No data returned from yfinance.")
            return

        # Access Close data
        # Check if MultiIndex or Single Level
        if isinstance(data.columns, pd.MultiIndex):
            close = data["VWCE.DE"]["Close"]
        else:
             close = data["Close"]

        print(f"Original Index Head (first 3): {close.index[:3]}")
        
        # Check if it has time components (non-midnight)
        has_time = any(t.hour != 0 or t.minute != 0 for t in close.index)
        print(f"Has non-midnight times: {has_time}")
        
        # Apply normalization (The Fix)
        if close.index.tz is not None:
             close.index = close.index.tz_localize(None)
        close.index = close.index.normalize()
        
        print(f"Normalized Index Head (first 3): {close.index[:3]}")
        
        # Verification: Create a daily date_range and try to intersect
        now = pd.Timestamp.now().normalize()
        daily_index = pd.date_range(start=start_date, end=now, freq="D")
        
        # Reindex check (simulating logic in app.py)
        # We need to ensure we don't get all NaNs
        reindexed = close.reindex(daily_index).ffill()
        
        non_nan_count = reindexed.count()
        print(f"Reindexed non-NaN count: {non_nan_count} / {len(reindexed)}")
        
        if non_nan_count > 0:
            print("SUCCESS: Data successfully reindexed with daily range.")
        else:
            print("FAILURE: Reindexing resulted in all NaNs (mismatch persisted).")

    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    verify_fix()
