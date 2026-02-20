import yfinance as yf

tickers = ['EUNK.DE', 'EUNK.SG', 'EUNK.F', 'IMAE.AS', 'IMEA.SW', 'EUNK.TI', 'SMEA.L', 'EUNK.MU', 'EUNKD.XC', 'EUNKD.XD', 'EUNK.DU', 'EUNKN.MX']

for t in tickers:
    try:
        price = yf.Ticker(t).fast_info.last_price
        print(f"{t}: {price}")
    except Exception as e:
        print(f"{t}: Error - {e}")
