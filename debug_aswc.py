#!/usr/bin/env python3
"""Debug script to check ASWC.DE price from various sources."""

import yfinance as yf

# Test yfinance
print("Testing yfinance for ASWC.DE...")
try:
    data = yf.download("ASWC.DE", period="1d", progress=False)
    if not data.empty:
        latest_price = data["Close"].iloc[-1]
        print(f"  yfinance ASWC.DE: €{latest_price:.3f}")
    else:
        print("  yfinance: No data returned")
except Exception as e:
    print(f"  yfinance error: {e}")

# Test alternatives
print("\nTesting alternative tickers...")
for ticker in ["ASWC.F", "ASWC.SG"]:
    try:
        data = yf.download(ticker, period="1d", progress=False)
        if not data.empty:
            latest_price = data["Close"].iloc[-1]
            print(f"  {ticker}: €{latest_price:.3f}")
        else:
            print(f"  {ticker}: No data")
    except:
        pass

# Expected: €16.706
print("\nExpected from DeGiro: €16.706")
