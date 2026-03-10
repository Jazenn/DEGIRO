import pandas as pd
import streamlit as st

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
        st.rerun()

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    DRIVE_FOLDER_ID = "16Y7kU4XDSbDjMUfBWU5695FSUWYjq26N"
    drive = None
    df_drive = pd.DataFrame()
    use_drive = False
    
    try:
        drive = DriveStorage(st.secrets["connections"]["gsheets"], DRIVE_FOLDER_ID)
        df_drive = drive.load_data()
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
                f.seek(0)
                df_part = load_degiro_csv(f)
                if not df_part.empty:
                    df_list.append(df_part)
            except Exception as e:
                st.error(f"Fout bij inlezen van '{f.name}': {e}")
        
        if df_list:
            df_new = pd.concat(df_list, ignore_index=True)

    df_raw = pd.DataFrame()
    
    if not df_drive.empty:
        for col in ["date", "value_date"]:
            if col in df_drive.columns:
                df_drive[col] = pd.to_datetime(df_drive[col], errors="coerce")
        df_raw = pd.concat([df_raw, df_drive], ignore_index=True)
        
    if not df_new.empty:
        df_raw = pd.concat([df_raw, df_new], ignore_index=True)

    if df_raw.empty:
        st.warning("Geen data gevonden. Upload een bestand of koppel aan Google Drive.")
        return
    
    if use_drive:
        st.sidebar.markdown("---")
        with st.sidebar.expander("🗑️ Data Beheer"):
            if st.button("🔴 Wis ALLE data", help="Verwijdert alle data uit Drive en leegt de uploader."):
                try:
                    empty_df = pd.DataFrame(columns=df_raw.columns)
                    drive.save_data(empty_df)
                    st.cache_data.clear()
                    st.session_state["uploader_key"] += 1
                    st.toast("Alle data is gewist!", icon="🗑️")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Kon data niet wissen: {e}")
    
    def _make_dedup_key(df_in: pd.DataFrame) -> pd.Series:
        d = pd.to_datetime(df_in["date"], errors='coerce').dt.strftime("%Y%m%d").fillna("00000000")
        t = df_in["time"].astype(str).str.strip().fillna("00:00")
        p_val = df_in["isin"].fillna(df_in["product"]).astype(str).str.strip().str.lower().replace("nan", "")
        
        def _clean_desc(s):
            s = str(s).strip().lower()
            if any(x in s for x in ["vanguard", "future", "hanetf"]):
                return s[:15]
            return s
        
        desc = df_in["description"].apply(_clean_desc)
        v = pd.to_numeric(df_in["amount"], errors="coerce").fillna(0.0).round(2).astype(str)
        oid = df_in["order_id"].astype(str).str.strip().fillna("")
        
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
        df_raw = df_raw[~df_raw["product"].astype(str).str.contains("Aegon", case=False, na=False)]

    def smart_numeric_clean(series):
        if pd.api.types.is_numeric_dtype(series):
             return series.fillna(0.0)
             
        nums = pd.to_numeric(series, errors='coerce')
        mask_fail = nums.isna() & series.notna()
        
        if mask_fail.any():
            def clean_eu(x):
                s = str(x).replace("EUR", "").replace("USD", "").strip()
                s = s.replace(".", "").replace(",", ".")
                return s
            
            cleaned = series[mask_fail].apply(clean_eu)
            nums.update(pd.to_numeric(cleaned, errors='coerce'))
            
        return nums.fillna(0.0)

    for col in ["amount", "balance", "fx"]:
        if col in df_raw.columns:
            df_raw[col] = smart_numeric_clean(df_raw[col])

    df = enrich_transactions(df_raw)
    
    # Generate product_map once to pass into cached history function
    product_map = {}
    if not df.empty and "product" in df.columns:
        for p in df["product"].unique():
            if not p: continue
            isin_series = df.loc[df["product"] == p, "isin"]
            isin_val = isin_series.iloc[0] if not isin_series.empty else None
            isin = str(isin_val).strip() if isin_val and pd.notna(isin_val) else None
            
            ticker = price_manager.resolve_ticker(p, isin)
            if ticker:
                product_map[p] = ticker

    history_df = build_portfolio_history(df, product_map=product_map)
    trading_volume = build_trading_volume_by_month(df)
    
    render_metrics(df, price_manager=price_manager, config_manager=config_manager)
    render_charts(df, history_df, trading_volume, drive=drive, config_manager=config_manager, price_manager=price_manager)
    
if __name__ == "__main__":
    main()
