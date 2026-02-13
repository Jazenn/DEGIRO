import pandas as pd
from app import calc_daily, pct_calc

rows = [
    {"ticker":"VWCE.DE","last_price":100.0,"quantity":10,"prev_close":98.0,"tradegate_price":97.0,"midnight_price":pd.NA},
    {"ticker":"BTC-USD","last_price":20000.0,"quantity":1,"prev_close":19500.0,"midnight_price":19800.0},
]
for r in rows:
    print(r, "daily_pl", calc_daily(pd.Series(r)), "daily_pct", pct_calc(pd.Series(r)))
