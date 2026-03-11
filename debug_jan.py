import pandas as pd
import toml
from drive_utils import DriveStorage
from data_processing import enrich_transactions, build_portfolio_history, build_global_invested_history
from managers import ConfigManager

def analyze():
    import json
    try:
        with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
            secrets = toml.load(f)
            creds = secrets.get("connections", {}).get("gsheets", {})
        
        DRIVE_FOLDER_ID = "16Y7kU4XDSbDjMUfBWU5695FSUWYjq26N"
        drive = DriveStorage(creds, DRIVE_FOLDER_ID)
        df_raw = drive.load_data()
        
        if df_raw.empty:
            print("No data in Drive.")
            return

        for col in ["date", "value_date"]:
             if col in df_raw.columns:
                 df_raw[col] = pd.to_datetime(df_raw[col], errors="coerce")
                 
        config = ConfigManager(drive=drive)
        product_map = config.get_mappings()
        
        df = enrich_transactions(df_raw)
        
        # Build portfolio history
        history_df = build_portfolio_history(df, product_map)
        
        # Build global invested
        global_inv = build_global_invested_history(df)
        
        # Merge them
        ttl_history = history_df.groupby("date").agg({"value": "sum"}).sort_index()
        ttl_history["invested"] = ttl_history.index.map(lambda d: global_inv.get(d.normalize(), pd.NA))
        ttl_history["invested"] = ttl_history["invested"].ffill().fillna(0.0)
        ttl_history["cum_pl"] = ttl_history["value"] - ttl_history["invested"]
        
        # Filter for Jan 10 to Jan 25
        jan_data = ttl_history[(ttl_history.index >= "2026-01-10") & (ttl_history.index <= "2026-01-25")]
        print("--- Portfolio Totals (Value vs Invested) ---")
        print(jan_data)
        
        print("\n--- Transactions on Jan 16 ---")
        jan16_tx = df[(df["value_date"].dt.normalize() == "2026-01-16")]
        print(jan16_tx[["value_date", "product", "type", "amount", "quantity", "price"] if "price" in jan16_tx else ["value_date", "product", "type", "amount", "quantity"]])
        
        print("\n--- History_df for Jan 15 and 16 ---")
        jan15_16_hist = history_df[(history_df["date"].dt.normalize() >= "2026-01-15") & (history_df["date"].dt.normalize() <= "2026-01-16")]
        print(jan15_16_hist[["date", "product", "quantity", "price", "value"]])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    analyze()
