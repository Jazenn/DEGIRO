from managers import PriceManager, ConfigManager
import streamlit as st

def test_prices():
    pm = PriceManager(ConfigManager())
    print("Testing Crypto Midnight Prices (UTC Baseline):")
    mid_prices = pm.get_midnight_prices_batch(["BTC-EUR", "ETH-EUR"])
    print(f"Midnight prices: {mid_prices}")
    
    # Expected approximately 60327 for BTC
    # Expected approximately 1754 for ETH
    
    print("\nTesting ETF Prev Closes:")
    prev_closes = pm.get_prev_closes_batch(["VWCE.DE", "ASWC.DE"])
    print(f"Prev Closes: {prev_closes}")

if __name__ == '__main__':
    st.cache_data.clear()
    test_prices()
