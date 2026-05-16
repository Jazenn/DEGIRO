import os
import sys
import pandas as pd
import traceback

from db_utils import DBStorage
from managers import ConfigManager, PriceManager
from data_processing import enrich_transactions, build_portfolio_history


def main():
    print("Starting DEGIRO background pre-fetcher...")
    try:
        db = DBStorage()

        df_raw = db.load_transactions()
        if df_raw.empty:
            print("Geen transacties gevonden in de database. Stoppen.")
            return

        print(f"Geladen: {len(df_raw)} transacties. Verrijken...")

        # Filter interne DEGIRO/Flatex kasrekeningen
        if "product" in df_raw.columns:
            df_raw = df_raw[~df_raw["product"].astype(str).str.contains("Aegon", case=False, na=False)]
        if "isin" in df_raw.columns:
            df_raw = df_raw[~df_raw["isin"].astype(str).str.contains("NLFLATEXACNT", case=False, na=False)]

        df = enrich_transactions(df_raw)

        config_manager = ConfigManager(db=db)
        price_manager = PriceManager(config_manager=config_manager)

        # Bouw product → ticker mapping
        product_map = {}
        if "product" in df.columns:
            for p in df["product"].dropna().unique():
                if not p:
                    continue
                isin_series = df.loc[df["product"] == p, "isin"]
                isin_val = isin_series.iloc[0] if not isin_series.empty else None
                isin = str(isin_val).strip() if isin_val and pd.notna(isin_val) else None
                ticker = price_manager.resolve_ticker(p, isin)
                if ticker:
                    product_map[p] = ticker

        unique_tickers = list(set(product_map.values()))
        print(f"Gevonden: {len(unique_tickers)} tickers. Live koersen ophalen...")

        batch_live  = price_manager.get_live_prices_batch(unique_tickers)
        batch_prev  = price_manager.get_prev_closes_batch(unique_tickers)
        batch_mid   = price_manager.get_midnight_prices_batch(unique_tickers)
        batch_open  = price_manager.get_market_open_prices_batch(unique_tickers)

        snapshot_prices = {
            "batch_live":  batch_live,
            "batch_prev":  batch_prev,
            "batch_mid":   batch_mid,
            "batch_open":  batch_open,
            "timestamp":   str(pd.Timestamp.now(tz="UTC")),
        }

        db.save_snapshot("prices", snapshot_prices)
        print("snapshot_prices opgeslagen in database.")

        print("Portfolio geschiedenis ophalen...")
        history_df = build_portfolio_history(df, product_map=product_map)

        if not history_df.empty:
            db.save_history_df(history_df)
            print(f"snapshot_history opgeslagen ({len(history_df)} rijen).")
        else:
            print("Waarschuwing: history_df is leeg — niet opgeslagen.")

        print("Fetcher succesvol afgerond.")

    except Exception:
        print("Fout tijdens fetcher:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
ry:
        main()
    except Exception:
        sys.exit(1)
