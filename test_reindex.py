import pandas as pd
import yfinance as yf

# Mock data_processing logic piece
start_date = (pd.Timestamp.now() - pd.Timedelta(days=10)).normalize()
now = pd.Timestamp.now().normalize()
daily_idx = pd.date_range(start=start_date, end=now, freq="D")

print("Fetching VWCE.DE (Stock/ETF, no weekends)")
hist = yf.download("VWCE.DE", start=start_date.strftime('%Y-%m-%d'))
hist = hist.copy()
if isinstance(hist.columns, pd.MultiIndex):
    hist = hist['Close']
else:
    hist = hist[['Close']].rename(columns={'Close': 'price'})
    hist.index = hist.index.tz_localize(None)

print("\nOriginal Hist Index:")
print(hist.index)

# Fixing logic: resample to D, ffill, then reindex
hist_eod = hist.resample('D').last().ffill()
hist_eod = hist_eod.reindex(daily_idx, method='ffill')

print("\nFixed Hist Index:")
print(hist_eod.index)
print(hist_eod)
