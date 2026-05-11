import pandas as pd
import streamlit as st
import time

from db_utils import DBStorage
from managers import ConfigManager, PriceManager
from data_processing import (
    load_degiro_csv,
    enrich_transactions,
    build_trading_volume_by_month,
    build_portfolio_history,
)
from ui_components import render_metrics, render_charts


def main() -> None:
    st.set_page_config(page_title="DeGiro Portfolio Dashboard", layout="wide")
    st.title("DeGiro Portfolio Dashboard")

    sidebar = st.sidebar
    sidebar.header("Instellingen")

    if sidebar.button("🔄 Ververs Koersen Nu", use_container_width=True,
                      help="Forceer een vernieuwing van alle live koersen."):
        st.cache_data.clear()
        st.session_state["live_fetch_done"] = False
        st.rerun()

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    # ------------------------------------------------------------------
    # 1. Database verbinding
    # ------------------------------------------------------------------
    db = None
    db_ok = False
    df_db = pd.DataFrame()

    try:
        db = DBStorage()
        df_db = db.load_transactions()
        db_ok = True
        sidebar.success("✅ Verbonden met database")
    except Exception as e:
        sidebar.error(f"Database verbindingsfout: {e}")
        sidebar.info("ℹ️ Voeg DATABASE_URL toe aan `.streamlit/secrets.toml`.")

    config_manager = ConfigManager(db=db)
    price_manager = PriceManager(config_manager=config_manager)

    # ------------------------------------------------------------------
    # 2. CSV uploader
    # ------------------------------------------------------------------
    uploaded_files = sidebar.file_uploader(
        "Upload DEGIRO CSV export",
        accept_multiple_files=True,
        key=f"uploader_{st.session_state['uploader_key']}",
        help="Upload de 'Account.csv' of 'Transactions.csv' export van DEGIRO.",
    )

    df_new = pd.DataFrame()
    if uploaded_files:
        df_list = []
        for f in uploaded_files:
            if not f.name.lower().endswith(".csv"):
                continue
            try:
                df_part = load_degiro_csv(f.getvalue())
                if not df_part.empty:
                    df_list.append(df_part)
            except Exception as e:
                st.error(f"Fout bij inlezen van '{f.name}': {e}")
        if df_list:
            df_new = pd.concat(df_list, ignore_index=True)

    # ------------------------------------------------------------------
    # 3. Samenvoegen: DB + nieuwe uploads
    #    Deduplicatie gebeurt in de DB via row_hash (ON CONFLICT DO NOTHING)
    # ------------------------------------------------------------------
    if db_ok and not df_new.empty:
        try:
            inserted = db.save_transactions(df_new)
            if inserted > 0:
                st.toast(f"✅ {inserted} nieuwe transacties opgeslagen!", icon="💾")
                st.cache_data.clear()
                # Herlaad vanuit DB zodat df_db de volledige dataset heeft
                df_db = db.load_transactions()
                # Reset uploader zodat de gebruiker weet dat de upload klaar is
                st.session_state["uploader_key"] += 1
                st.rerun()
            else:
                st.toast("Geen nieuwe transacties gevonden (alles al aanwezig).", icon="🧹")
        except Exception as e:
            st.error(f"Opslaan naar database mislukt: {e}")

    # df_raw is de gecombineerde dataset
    df_raw = df_db.copy() if not df_db.empty else df_new.copy()

    if df_raw.empty:
        st.warning("Geen data gevonden. Upload een DEGIRO CSV of koppel de database.")
        return

    # ------------------------------------------------------------------
    # 4. Filter interne DEGIRO-rekeningen (geen echte posities)
    # ------------------------------------------------------------------
    if "product" in df_raw.columns:
        df_raw = df_raw[
            ~df_raw["product"].astype(str).str.contains("Aegon", case=False, na=False)
        ]
    if "isin" in df_raw.columns:
        df_raw = df_raw[
            ~df_raw["isin"].astype(str).str.contains("NLFLATEXACNT", case=False, na=False)
        ]

    # ------------------------------------------------------------------
    # 5. Data Beheer sidebar
    # ------------------------------------------------------------------
    if db_ok:
        sidebar.markdown("---")
        with sidebar.expander("🗑️ Data Beheer"):
            st.caption(
                "Snapshots bevatten gecachede koersen en historische data. "
                "Reset ze als de dashboard verkeerde waarden toont."
            )
            if st.button("🔄 Reset Snapshots", use_container_width=True,
                         help="Wist koersen- en historische snapshots. Transacties en configuratie blijven."):
                try:
                    db.clear_snapshot("prices")
                    db.clear_snapshot("history")
                    for key in ["snapshot_prices", "snapshot_history", "live_fetch_done",
                                "mem_live_prices", "mem_prev_prices", "mem_open_prices", "mem_mid_prices"]:
                        st.session_state.pop(key, None)
                    st.cache_data.clear()
                    st.toast("Snapshots gereset!", icon="🔄")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Snapshots resetten mislukt: {e}")

            st.markdown("---")
            if st.button("🔴 Wis ALLE transactiedata", use_container_width=True,
                         help="Verwijdert alle transacties uit de database. Configuratie en targets blijven."):
                try:
                    db.clear_transactions()
                    st.cache_data.clear()
                    st.session_state["uploader_key"] += 1
                    st.toast("Alle transactiedata gewist!", icon="🗑️")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Wissen mislukt: {e}")

    # ------------------------------------------------------------------
    # 6. Verrijken
    # ------------------------------------------------------------------
    df = enrich_transactions(df_raw)

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

    # ------------------------------------------------------------------
    # 7. Snapshots laden vanuit DB
    # ------------------------------------------------------------------
    if "snapshot_prices" not in st.session_state and db_ok:
        st.session_state["snapshot_prices"] = db.load_snapshot("prices")
    if "snapshot_history" not in st.session_state and db_ok:
        hst = db.load_history_df()
        st.session_state["snapshot_history"] = hst if not hst.empty else None

    snap_prices  = st.session_state.get("snapshot_prices")
    snap_history = st.session_state.get("snapshot_history")

    # Stale snapshot guard — meer dan 6 uur oud → live fetch forceren
    _SNAPSHOT_MAX_AGE_HOURS = 6
    if snap_prices and "timestamp" in snap_prices:
        try:
            snap_ts   = pd.Timestamp(snap_prices["timestamp"])
            age_hours = (pd.Timestamp.now(tz="UTC") - snap_ts).total_seconds() / 3600
            if age_hours > _SNAPSHOT_MAX_AGE_HOURS:
                snap_prices = None
                st.session_state["snapshot_prices"] = None
                st.session_state["live_fetch_done"]  = False
                sidebar.warning(
                    f"⚠️ Koersen verlopen ({age_hours:.1f}u oud). Live data wordt opgehaald..."
                )
        except Exception:
            pass

    if snap_prices:
        price_manager.load_snapshots(snap_prices)
        if "timestamp" in snap_prices:
            sidebar.caption(f"⏱️ Laatste sync: {snap_prices['timestamp'][:16]} UTC")

    if snap_history is not None and not snap_history.empty:
        history_df = snap_history
    else:
        history_df = build_portfolio_history(df, product_map=product_map)

    trading_volume = build_trading_volume_by_month(df)

    # ------------------------------------------------------------------
    # 8. Renderen
    # ------------------------------------------------------------------
    render_metrics(df, price_manager=price_manager, config_manager=config_manager)
    render_charts(
        df, history_df, trading_volume,
        drive=None,           # Drive niet meer gebruikt
        config_manager=config_manager,
        price_manager=price_manager,
        db=db,
    )

    # ------------------------------------------------------------------
    # 9. Achtergrond koersen verversen
    # ------------------------------------------------------------------
    if not st.session_state.get("live_fetch_done", False) or st.session_state.get("force_refresh", False):
        @st.fragment
        def background_swapper():
            unique_tickers = list(set(product_map.values()))
            if not unique_tickers:
                return

            if st.session_state.get("force_refresh", False):
                price_manager._fetch_live_prices_batch_cached.clear()
                price_manager._fetch_prev_closes_batch_cached.clear()
                price_manager._fetch_market_open_prices_batch_cached.clear()
                price_manager._fetch_midnight_prices_batch_cached.clear()

            batch_live = price_manager._fetch_live_prices_batch_cached(tuple(unique_tickers))
            ams_today  = pd.Timestamp.now(tz="Europe/Amsterdam").strftime("%Y-%m-%d")
            batch_prev = price_manager._fetch_prev_closes_batch_cached(tuple(unique_tickers), ams_today)
            batch_open = price_manager._fetch_market_open_prices_batch_cached(tuple(unique_tickers))
            midnight_ams = pd.Timestamp.now(tz="Europe/Amsterdam").normalize()
            date_str   = midnight_ams.strftime("%Y-%m-%d %H:%M:%S %Z")
            batch_mid  = price_manager._fetch_midnight_prices_batch_cached(tuple(unique_tickers), date_str)

            st.session_state["mem_live_prices"] = batch_live
            st.session_state["mem_prev_prices"] = batch_prev
            st.session_state["mem_open_prices"] = batch_open
            st.session_state["mem_mid_prices"]  = batch_mid

            # Sla verse snapshot op in DB
            if db_ok:
                try:
                    db.save_snapshot("prices", {
                        "batch_live":  batch_live,
                        "batch_prev":  batch_prev,
                        "batch_mid":   batch_mid,
                        "batch_open":  batch_open,
                        "timestamp":   str(pd.Timestamp.now(tz="UTC")),
                    })
                    st.session_state["snapshot_prices"] = db.load_snapshot("prices")
                except Exception:
                    pass

            st.session_state["live_fetch_done"] = True
            st.session_state["force_refresh"]   = False
            st.rerun()

        background_swapper()


if __name__ == "__main__":
    main()
