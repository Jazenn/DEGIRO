from managers import ConfigManager, PriceManager

cm = ConfigManager()
pm = PriceManager(cm)

# Simulate what DeGiro gives us
product_str = "iShares Core MSCI Europe UCITS ETF EUR (Acc)"
isin = "IE00B4K48X80"

resolved = pm.resolve_ticker(product_str=product_str, isin=isin)
print(f"Testing EUNK resolution:")
print(f"Product: {product_str}")
print(f"ISIN: {isin}")
print(f"Resolved Ticker: {resolved}")
print(f"Mapping saved: {cm.get_ticker_for_product(None, isin)}")
