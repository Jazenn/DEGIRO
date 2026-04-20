import os
import sys
import pandas as pd
import traceback

from drive_utils import DriveStorage
from managers import ConfigManager, PriceManager
from data_processing import enrich_transactions, build_portfolio_history

def main():
    print("Starting DEGIRO background pre-fetcher...")
    try:
        DRIVE_FOLDER_ID = "16Y7kU4XDSbDjMUfBWU5695FSUWYjq26N"
        drive = DriveStorage(DRIVE_FOLDER_ID)
        df_drive = drive.load_data()
        
        if df_drive.empty:
            print("No data found in drive. Exiting.")
            sys.exit(0)
            
        print("Loaded transactions from Drive. Enriching...")
        df_raw = df_drive.copy()
        for col in ["date", "value_date"]:
            if col in df_raw.columns:
                df_raw[col] = pd.to_datetime(df_raw[col], errors="coerce")
                
        def smart_numeric_clean(series):
            if pd.api.types.is_numeric_dtype(series): return series.fillna(0.0)
            nums = pd.to_numeric(series, errors='coerce')
            mask_fail = nums.isna() & series.notna()
            if mask_fail.any():
                def clean_eu(x): return str(x).replace("EUR", "").replace("USD", "").strip().replace(".", "").replace(",", ".")
                cleaned = series[mask_fail].apply(clean_eu)
                nums.update(pd.to_numeric(cleaned, errors='coerce'))
            return nums.fillna(0.0)

        for col in ["amount", "balance", "fx"]:
            if col in df_raw.columns: df_raw[col] = smart_numeric_clean(df_raw[col])
            
        df = enrich_transactions(df_raw)
        
        config_manager = ConfigManager(drive=drive)
        price_manager = PriceManager(config_manager=config_manager)
        
        product_map = {}
        if "product" in df.columns:
            for p in df["product"].unique():
                if not p: continue
                isin_series = df.loc[df["product"] == p, "isin"]
                isin_val = isin_series.iloc[0] if not isin_series.empty else None
                isin = str(isin_val).strip() if isin_val and pd.notna(isin_val) else None
                
                ticker = price_manager.resolve_ticker(p, isin)
                if ticker:
                    product_map[p] = ticker

        unique_tickers = list(set(product_map.values()))
        print(f"Discovered {len(unique_tickers)} tickers. Fetching live prices...")
        
        # Batch fetch all prices
        batch_live = price_manager.get_live_prices_batch(unique_tickers)
        batch_prev = price_manager.get_prev_closes_batch(unique_tickers)
        batch_mid = price_manager.get_midnight_prices_batch(unique_tickers)
        batch_open = price_manager.get_market_open_prices_batch(unique_tickers)
        
        snapshot_prices = {
            "batch_live": batch_live,
            "batch_prev": batch_prev,
            "batch_mid": batch_mid,
            "batch_open": batch_open,
            "timestamp": str(pd.Timestamp.now(tz="UTC"))
        }
        
        drive.save_json("snapshot_prices.json", snapshot_prices)
        print("Successfully saved snapshot_prices.json")
        
        print("Fetching portfolio history...")
        history_df = build_portfolio_history(df, product_map=product_map)
        
        if not history_df.empty:
            drive.save_csv("snapshot_history.csv", history_df)
            print("Successfully saved snapshot_history.csv")
        else:
            print("Warning: history_df empty.")
            
        print("Fetcher finished successfully.")
        
    except Exception as e:
        print("Error during fetch:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
