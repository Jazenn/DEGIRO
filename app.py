import pandas as pd
import streamlit as st
import os
import time
from drive_utils import DriveStorage
from managers import ConfigManager, PriceManager
from data_processing import (
    load_degiro_csv,
    enrich_transactions,
    build_trading_volume_by_month,
    build_portfolio_history
)
from ui_components import render_metrics, render_charts

def main() -> None:
    st.set_page_config(
        page_title="DeGiro Portfolio Dashboard",
        layout="wide",
    )

    st.title("DeGiro Portfolio Dashboard")
    
    sidebar = st.sidebar
    sidebar.header("Instellingen")

    if sidebar.button("🔄 Ververs Koersen Nu", use_container_width=True, help="Forceer een vernieuwing van alle live koersen."):
        st.cache_data.clear()
        st.session_state["live_fetch_done"] = False
        st.rerun()

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    DRIVE_FOLDER_ID = "16Y7kU4XDSbDjMUfBWU5695FSUWYjq26N"
    drive = None
    df_drive = pd.DataFrame()
    use_drive = False
    
    try:
        drive = DriveStorage(DRIVE_FOLDER_ID)
        # Load Drive CSV through the same pipeline as uploaded files so that
        # amount parsing, currency-column shifting, and Unnamed cleanup all apply.
        drive_bytes = drive.load_data_bytes()
        if drive_bytes and len(drive_bytes) > 10:
            df_drive = load_degiro_csv(drive_bytes)
        use_drive = True
        sidebar.success("✅ Verbonden met Google Drive (CSV)")
    except Exception as e:
        import traceback
        sidebar.error(f"Fout met verbinden Google Drive: {e}")
        sidebar.code(traceback.format_exc())
        sidebar.info("ℹ️ Google Drive niet gekoppeld. Data wordt niet opgeslagen.")
        with sidebar.expander("Hoe te koppelen?"):
             st.markdown(
                 "Om data op te slaan, voeg je Google Service Account credentials toe "
                 "aan `.streamlit/secrets.toml`."
             )

    config_manager = ConfigManager(drive=drive)
    price_manager = PriceManager(config_manager=config_manager)

    uploaded_files = sidebar.file_uploader(
        "Upload nieuwe CSV's (optioneel)",
        accept_multiple_files=True,
        key=f"uploader_{st.session_state['uploader_key']}",
        help="Nieuwe bestanden worden toegevoegd aan de opgeslagen data."
    )

    df_new = pd.DataFrame()
    if uploaded_files:
        df_list = []
        for f in uploaded_files:
            if not f.name.lower().endswith(".csv"):
                continue
            try:
                file_bytes = f.getvalue()  # read once as bytes — safe for @st.cache_data
                df_part = load_degiro_csv(file_bytes)
                if not df_part.empty:
                    df_list.append(df_part)
            except Exception as e:
                st.error(f"Fout bij inlezen van '{f.name}': {e}")
        
        if df_list:
            df_new = pd.concat(df_list, ignore_index=True)

    df_raw = pd.DataFrame()

    if not df_drive.empty:
        df_raw = pd.concat([df_raw, df_drive], ignore_index=True)

    if not df_new.empty:
        df_raw = pd.concat([df_raw, df_new], ignore_index=True)

    if df_raw.empty:
        st.warning("Geen data gevonden. Upload een bestand of koppel aan Google Drive.")
        return
    
    if use_drive:
        st.sidebar.markdown("---")
        with st.sidebar.expander("🗑️ Data Beheer"):
            st.caption("Snapshots bevatten gecachede koersen en historische data. Reset ze als de dashboard verkeerde waarden toont.")
            if st.button("🔄 Reset Snapshots", help="Wist snapshot_history.csv en snapshot_prices.json. Transacties en configuratie blijven bewaard.", use_container_width=True):
                try:
                    # Save empty CSVs/JSONs to overwrite the corrupt snapshots
                    drive.save_json("snapshot_prices.json", {})
                    drive.save_csv("snapshot_history.csv", pd.DataFrame())
                    # Clear all session state snapshot keys
                    for key in ["snapshot_prices", "snapshot_history", "live_fetch_done",
                                "mem_live_prices", "mem_prev_prices", "mem_open_prices", "mem_mid_prices"]:
                        st.session_state.pop(key, None)
                    st.cache_data.clear()
                    st.toast("Snapshots gereset! Koersen worden opnieuw opgehaald.", icon="🔄")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Kon snapshots niet resetten: {e}")

            st.markdown("---")
            if st.button("🔴 Wis ALLE transactiedata", help="Verwijdert transactions_master.csv uit Drive en leegt de uploader. Configuratie en targets blijven bewaard.", use_container_width=True):
                try:
                    empty_df = pd.DataFrame(columns=df_raw.columns)
                    drive.save_data(empty_df)
                    st.cache_data.clear()
                    st.session_state["uploader_key"] += 1
                    st.toast("Transactiedata gewist!", icon="🗑️")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Kon data niet wissen: {e}")
    
    def _make_dedup_key(df_in: pd.DataFrame) -> pd.Series:
        d = pd.to_datetime(df_in["date"], errors='coerce').dt.strftime("%Y%m%d").fillna("00000000")
        # time column may be missing in some exports
        if "time" in df_in.columns:
            t = df_in["time"].astype(str).str.strip().replace("nan", "00:00").fillna("00:00")
        else:
            t = pd.Series("00:00", index=df_in.index)
        # Use ISIN if available, fall back to product, strip NaN representations
        p_val = (
            df_in["isin"].fillna(df_in["product"])
            .astype(str).str.strip().str.lower()
            .str.replace(r"^nan$", "", regex=True)
        )
        
        def _clean_desc(s):
            s = str(s).strip().lower()
            if any(x in s for x in ["vanguard", "future", "hanetf"]):
                return s[:15]
            return s
        
        desc = df_in["description"].apply(_clean_desc)
        v = pd.to_numeric(df_in["amount"], errors="coerce").fillna(0.0).round(2).astype(str)
        if "order_id" in df_in.columns:
            oid = df_in["order_id"].astype(str).str.strip().replace("nan", "").fillna("")
        else:
            oid = pd.Series("", index=df_in.index)
        
        return d + "|" + t + "|" + p_val + "|" + desc + "|" + v + "|" + oid

    before_dedup = len(df_raw)
    if not df_raw.empty:
        df_raw["_temp_key"] = _make_dedup_key(df_raw)
        df_raw = df_raw.drop_duplicates(subset=["_temp_key"])
        df_raw = df_raw.drop(columns=["_temp_key"])
    after_dedup = len(df_raw)
    
    if before_dedup != after_dedup and not df_new.empty:
        st.toast(f"{before_dedup - after_dedup} dubbele regels genegeerd.", icon="🧹")

    if use_drive and not df_new.empty:
        try:
            drive.save_data(df_raw)
            st.toast("Nieuwe data succesvol opgeslagen in Google Drive (CSV)!", icon="💾")
        except Exception as e:
            st.error(f"Fout bij opslaan naar Drive: {e}")
    
    if "product" in df_raw.columns:
        # Filter internal DEGIRO/Flatex accounts that appear as "products" but are
        # not real investable positions (cash sweep counterparty accounts).
        df_raw = df_raw[~df_raw["product"].astype(str).str.contains("Aegon", case=False, na=False)]
        df_raw = df_raw[~df_raw["isin"].astype(str).str.contains("NLFLATEXACNT", case=False, na=False)]

    df = enrich_transactions(df_raw)
    
    # Identify unique product mappings instantly
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

    # Try to load snapshots
    if "snapshot_prices" not in st.session_state and use_drive:
        st.session_state["snapshot_prices"] = drive.load_json("snapshot_prices.json")
    if "snapshot_history" not in st.session_state and use_drive:
        hst = drive.load_csv("snapshot_history.csv")
        if not hst.empty and "date" in hst.columns:
            hst["date"] = pd.to_datetime(hst["date"])
        st.session_state["snapshot_history"] = hst

    snap_prices = st.session_state.get("snapshot_prices")
    snap_history = st.session_state.get("snapshot_history")

    # --- Stale snapshot guard ---
    # If the snapshot is older than 6 hours, discard it so live prices are
    # fetched fresh. Crypto trades 24/7, so a stale midnight price from the
    # previous day causes the daily P/L to appear as €0.
    _SNAPSHOT_MAX_AGE_HOURS = 6
    if snap_prices and "timestamp" in snap_prices:
        try:
            snap_ts = pd.Timestamp(snap_prices["timestamp"])
            age_hours = (pd.Timestamp.now(tz="UTC") - snap_ts).total_seconds() / 3600
            if age_hours > _SNAPSHOT_MAX_AGE_HOURS:
                snap_prices = None
                st.session_state["snapshot_prices"] = None
                st.session_state["live_fetch_done"] = False  # force re-fetch
                st.sidebar.warning(f"⚠️ Koersen snapshot verlopen ({age_hours:.1f}u oud). Live data wordt opgehaald...")
        except Exception:
            pass
    
    if snap_prices:
        price_manager.load_snapshots(snap_prices)
        if "timestamp" in snap_prices:
            st.sidebar.caption(f"⏱️ Laatste Live Sync: {snap_prices['timestamp'][:16]} UTC")

    if snap_history is not None and not snap_history.empty:
        history_df = snap_history
    else:
        history_df = build_portfolio_history(df, product_map=product_map)

    trading_volume = build_trading_volume_by_month(df)
    
    render_metrics(df, price_manager=price_manager, config_manager=config_manager)
    render_charts(df, history_df, trading_volume, drive=drive, config_manager=config_manager, price_manager=price_manager)
    
    # Seamless background cache-warming
    if not st.session_state.get("live_fetch_done", False) or st.session_state.get("force_refresh", False):
        @st.fragment
        def background_swapper():
            unique_tickers = list(set(product_map.values()))
            if unique_tickers:
                if st.session_state.get("force_refresh", False):
                    price_manager._fetch_live_prices_batch_cached.clear()
                    price_manager._fetch_prev_closes_batch_cached.clear()
                    price_manager._fetch_market_open_prices_batch_cached.clear()
                    price_manager._fetch_midnight_prices_batch_cached.clear()
                    
                batch_live = price_manager._fetch_live_prices_batch_cached(tuple(unique_tickers))
                
                ams_today = pd.Timestamp.now(tz="Europe/Amsterdam").strftime("%Y-%m-%d")
                batch_prev = price_manager._fetch_prev_closes_batch_cached(tuple(unique_tickers), ams_today)
                
                batch_open = price_manager._fetch_market_open_prices_batch_cached(tuple(unique_tickers))
                
                midnight_ams = pd.Timestamp.now(tz="Europe/Amsterdam").normalize()
                date_str = midnight_ams.strftime("%Y-%m-%d %H:%M:%S %Z")
                batch_mid = price_manager._fetch_midnight_prices_batch_cached(tuple(unique_tickers), date_str)
                
                # Push into shared memory buffer to prevent ANY grey UI loading blocks
                st.session_state["mem_live_prices"] = batch_live
                st.session_state["mem_prev_prices"] = batch_prev
                st.session_state["mem_open_prices"] = batch_open
                st.session_state["mem_mid_prices"] = batch_mid

                # Push updated snapshot to Drive immediately for consistent UX
                try:
                    snapshot_prices = {
                        "batch_live": batch_live,
                        "batch_prev": batch_prev,
                        "batch_mid": batch_mid,
                        "batch_open": batch_open,
                        "timestamp": str(pd.Timestamp.now(tz="UTC"))
                    }
                    if use_drive:
                        drive.save_json("snapshot_prices.json", snapshot_prices)
                        st.session_state["snapshot_prices"] = snapshot_prices
                except Exception:
                    pass
            
            st.session_state["live_fetch_done"] = True
            st.session_state["force_refresh"] = False
            st.rerun()

        background_swapper()
        
if __name__ == "__main__":
    main()
