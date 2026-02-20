from managers import ConfigManager, PriceManager

cm = ConfigManager()
pm = PriceManager(cm)

print(f"Mapping for IE00BK5BQT80 initially: {cm.get_ticker_for_product(None, 'IE00BK5BQT80')}")

resolved = pm.resolve_ticker(product_str="VWCE", isin="IE00BK5BQT80")
print(f"Resolved IE00BK5BQT80 -> {resolved}")

print(f"Mapping after resolve: {cm.get_ticker_for_product(None, 'IE00BK5BQT80')}")

print("\nTesting an unknown stock 'NVDA'")
resolved_nvda = pm.resolve_ticker(product_str="NVIDIA", isin="US67066G1040")
print(f"Resolved US67066G1040 (NVDA) -> {resolved_nvda}")
print(f"Mapping after NVDA: {cm.get_ticker_for_product(None, 'US67066G1040')}")
