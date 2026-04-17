import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import format_eur, format_eur_smart, format_pct, _shorten_name, fragment, is_tradegate_open
from data_processing import build_positions, build_global_invested_history

@fragment(run_every=300)
def render_metrics(df: pd.DataFrame, price_manager, config_manager) -> None:
    """Render metrics with auto-refresh using PriceManager."""
    positions = build_positions(df)
    
    if not positions.empty:
        positions["ticker"] = positions.apply(
            lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1
        )
        
        unique_tickers = positions["ticker"].dropna().unique().tolist()
        batch_live = price_manager.get_live_prices_batch(unique_tickers)
        batch_prev = price_manager.get_prev_closes_batch(unique_tickers)
        batch_mid = price_manager.get_midnight_prices_batch(unique_tickers)
        batch_open = price_manager.get_market_open_prices_batch(unique_tickers)
        
        positions["last_price"] = positions["ticker"].map(lambda t: batch_live.get(t, 0.0))
        positions["prev_close"] = positions["ticker"].map(lambda t: batch_prev.get(t, 0.0))
        positions["midnight_price"] = positions["ticker"].map(lambda t: batch_mid.get(t, 0.0))
        positions["market_open"] = positions["ticker"].map(lambda t: batch_open.get(t, 0.0))
        
        positions["current_value"] = positions.apply(
            lambda r: (
                r["quantity"] * r["last_price"]
                if pd.notna(r.get("last_price")) and pd.notna(r.get("quantity"))
                else pd.NA
            ),
            axis=1,
        )

        def calc_daily_base(r):
            qty = r.get("quantity")
            if pd.isna(qty): return pd.NA
            
            is_crypto = str(r.get("isin", "")).startswith("XFC") or any(x in str(r.get("product", "")).upper() for x in ["BTC", "ETH", "COIN", "CRYPTO", "BITCOIN", "ETHEREUM"])
            
            if is_crypto:
                base = r.get("midnight_price")
            else:
                base = r.get("prev_close")
                
            if pd.isna(base) or base == 0:
                base = r.get("market_open")
            
            if pd.notna(base) and base > 0:
                return qty * base
            return pd.NA

        positions["daily_base_val"] = positions.apply(calc_daily_base, axis=1)
        total_daily_base = positions["daily_base_val"].dropna().sum() if not positions.empty else 0.0

        def calc_daily(r):
            lp = r.get("last_price")
            qty = r.get("quantity")
            if pd.isna(lp) or pd.isna(qty): return pd.NA
            
            # Hide non-crypto Daily P/L when market is closed
            is_crypto = str(r.get("isin", "")).startswith("XFC")
            if not is_crypto and not is_tradegate_open():
                return 0.0
            
            base_val = r.get("daily_base_val")
            if pd.notna(base_val) and base_val > 0 and pd.notna(lp) and lp > 0:
                return (lp * qty) - base_val
            return 0.0

        positions["daily_pl_eur"] = positions.apply(calc_daily, axis=1)
        total_daily_pl = positions["daily_pl_eur"].dropna().sum() if not positions.empty else 0.0
        daily_pct_total = (total_daily_pl / total_daily_base * 100.0) if total_daily_base > 0 else 0.0

        positions["avg_price"] = positions.apply(
            lambda r: (
                r["invested"] / r["quantity"]
                if pd.notna(r.get("invested"))
                and pd.notna(r.get("quantity"))
                and r["quantity"] != 0
                else pd.NA
            ),
            axis=1,
        )
    else:
        positions["ticker"] = []
        positions["last_price"] = []
        positions["prev_close"] = []
        positions["current_value"] = []
        positions["avg_price"] = []

    total_deposits = df.loc[df["type"] == "Deposit", "amount"].sum()
    total_withdrawals = -df.loc[df["type"] == "Withdrawal", "amount"].sum()
    
    total_buys = df.loc[df["type"] == "Buy", "amount"].sum()
    total_sells = df.loc[df["type"] == "Sell", "amount"].sum()
    
    total_fees = -df.loc[df["is_fee"], "amount"].sum()
    total_dividends = df.loc[df["is_dividend"], "amount"].sum()
    
    total_market_value = (
        positions["current_value"].dropna().sum() if not positions.empty else 0.0
    )
    
    valid_cash_tx = df[~df["type"].isin(["Reservation", "Cash Sweep"])]
    current_cash = valid_cash_tx["amount"].sum()
    
    total_costs = abs(total_buys) + total_fees - abs(total_sells) - total_dividends
    
    if not positions.empty:
        positions["pl_eur"] = positions.apply(
            lambda r: r.get("current_value", 0.0) + r.get("net_cashflow", 0.0),
            axis=1,
        )
        total_result = total_market_value - total_costs
    else:
        total_result = total_market_value - total_costs

    if pd.notna(total_costs) and total_costs != 0:
        pct_total = (total_result / abs(total_costs) * 100.0)
    else:
        pct_total = 0.0

    if "value_date" in df.columns and not df["value_date"].empty:
        min_date = df["value_date"].min()
        max_date = df["value_date"].max()
        period_str = f"{min_date.strftime('%B %Y')} - {max_date.strftime('%B %Y')}"
        now_str = pd.Timestamp.now(tz="Europe/Amsterdam").strftime("%d-%m-%Y %H:%M:%S")
        st.markdown(f"**Periode data:** {period_str} | **Laatst bijgewerkt:** {now_str}")
    
    current_balance = 0.0
    if not df.empty and "balance" in df.columns:
        if "csv_row_id" in df.columns:
            sorted_df = df.sort_values(["value_date", "csv_row_id"], ascending=[False, True])
        else:
            sorted_df = df.sort_values("value_date", ascending=False)
            
        latest_row = sorted_df.iloc[0]
        current_balance = latest_row.get("balance", 0.0)

    st.markdown("---")
    st.subheader("Dashboard Overzicht")

    col1, col2, col3, col_daily = st.columns(4)
    help_txt = (
        f"Aankopen: {format_eur(abs(total_buys))}  |  "
        f"Fees: {format_eur(total_fees)}  |  "
        f"Verkopen: -{format_eur(abs(total_sells))}  |  "
        f"Dividend: -{format_eur(total_dividends)}"
    )
    with col1.container(border=True):
        st.metric("Netto Inleg", format_eur(total_costs), help=help_txt)
    with col2.container(border=True):
        st.metric("Marktwaarde", format_eur(total_market_value))
    with col3.container(border=True):
        st.metric("Total P/L", format_eur(total_result), delta=format_pct(pct_total), delta_color="normal",
                   help="Berekening: Marktwaarde - Totale kosten")
    with col_daily.container(border=True):
        daily_color = "normal" if pd.notna(total_daily_pl) else "off"
        st.metric("Dag W/V", format_eur(total_daily_pl) if pd.notna(total_daily_pl) else "€ 0,00", delta=format_pct(daily_pct_total) if pd.notna(total_daily_pl) else None, delta_color=daily_color, help="Dagelijks resultaat gebaseerd op de vorige slotkoers (of middernacht voor crypto).")
    
    col4, col5 = st.columns(2)
    with col4.container(border=True):
        st.metric("Vrije Ruimte (Saldo)", format_eur(current_balance), help="Het laatst bekende saldo uit de transactiehistorie.")
    with col5.container(border=True):
        st.metric("Ontvangen dividend", format_eur(total_dividends))
        
    st.divider()

@fragment(run_every=300)
def render_overview(df: pd.DataFrame, config_manager, price_manager) -> None:
    """Render de open posities tabel en allocatie chart met auto-refresh."""
    positions = build_positions(df)
    
    if not positions.empty:
        positions["ticker"] = positions.apply(
            lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1
        )
        
        unique_tickers = positions["ticker"].dropna().unique().tolist()
        batch_live = price_manager.get_live_prices_batch(unique_tickers)
        batch_mid = price_manager.get_midnight_prices_batch(unique_tickers)
        batch_open = price_manager.get_market_open_prices_batch(unique_tickers)
        positions["last_price"] = positions["ticker"].map(lambda t: batch_live.get(t, 0.0))
        positions["midnight_price"] = positions["ticker"].map(lambda t: batch_mid.get(t, 0.0))
        positions["market_open"] = positions["ticker"].map(lambda t: batch_open.get(t, 0.0))

        positions["current_value"] = positions.apply(
            lambda r: (
                r["quantity"] * r["last_price"]
                if pd.notna(r.get("last_price")) and pd.notna(r.get("quantity"))
                else pd.NA
            ),
            axis=1,
        )
        
        positions["Category"] = positions["isin"].apply(lambda x: "Crypto" if str(x).startswith("XFC") else "ETFs & Stocks")
        positions["Display Name"] = positions["product"].apply(_shorten_name)
        
        st.subheader("Open posities (afgeleid uit transacties)")
        
        for cat in ["ETFs & Stocks", "Crypto"]:
            cat_df = positions[positions["Category"] == cat].copy()
            if not cat_df.empty:
                st.markdown(f"#### {cat}")
                display = cat_df.copy()
                
                batch_prev = price_manager.get_prev_closes_batch(display["ticker"].dropna().unique().tolist())
                display["prev_close"] = display["ticker"].map(lambda t: batch_prev.get(t, 0.0))
                
                def calc_daily_display(row):
                    lp = row.get("last_price")
                    qty = row.get("quantity")
                    if pd.isna(lp) or pd.isna(qty): return pd.NA, pd.NA
                    
                    if cat == "Crypto":
                        base = row.get("midnight_price")
                    else:
                        base = row.get("prev_close")
                        # Hide non-crypto Daily P/L when market is closed
                        if not is_tradegate_open():
                            return 0.0, 0.0
                        
                    if pd.isna(base) or base == 0:
                        base = row.get("market_open")
                        
                    if pd.notna(base) and base > 0 and pd.notna(lp) and lp > 0:
                        pl_eur = qty * (lp - base)
                        base_val = qty * base
                        pl_pct = (pl_eur / base_val * 100.0) if base_val > 0 else 0.0
                        return pl_eur, pl_pct
                    return 0.0, 0.0
                    
                display[["Dag W/V (EUR)", "Dag W/V (%)"]] = display.apply(calc_daily_display, axis=1, result_type="expand")

                buy_val = display["invested"]
                sell_val = display["total_sells"].fillna(0.0)
                fee_val = display["total_fees"].abs().fillna(0.0)
                div_val = display["total_dividends"].fillna(0.0)
                
                display["Totaal geinvesteerd"] = (buy_val + fee_val - sell_val - div_val)
                
                display["Winst/verlies (EUR)"] = (display["current_value"] + display["net_cashflow"])
                
                display["Totaal geinvesteerd"] = display["Totaal geinvesteerd"].map(format_eur)
                display["Huidige waarde"] = display["current_value"].map(format_eur)
                display["Winst/verlies (EUR)"] = display["Winst/verlies (EUR)"].map(format_eur)
                
                def fmt_daily(val):
                    if pd.isna(val): return "€ 0,00"
                    return format_eur(val)
                def fmt_daily_pct(val):
                    if pd.isna(val): return "0,00%"
                    return format_pct(val)
                display["Dag W/V (EUR)_fmt"] = display["Dag W/V (EUR)"].apply(fmt_daily)
                display["Dag W/V (%)_fmt"] = display["Dag W/V (%)"].apply(fmt_daily_pct)

                def _pl_pct(row: pd.Series) -> float | None:
                    cur = row.get("current_value")
                    net_cf = row.get("net_cashflow")
                    
                    inv = row.get("invested", 0)
                    fees = abs(row.get("total_fees", 0))
                    sells = row.get("total_sells", 0)
                    divs = row.get("total_dividends", 0)
                    
                    cost_basis = inv + fees - sells - divs
                    
                    if pd.notna(cur) and pd.notna(net_cf):
                        pl_amount = cur + net_cf
                        if cost_basis != 0:
                            return (pl_amount / cost_basis) * 100.0
                    return pd.NA

                display["Winst/verlies (%)"] = display.apply(_pl_pct, axis=1).map(format_pct)

                for _, row in display.iterrows():
                    product_name = row["Product"] if "Product" in row else row.get("Display Name", "Onbekend")
                    
                    result_raw = row.get("Winst/verlies (EUR)", "€ 0,00")
                    result_pct = row.get("Winst/verlies (%)", "0,00%")
                    current_val = row.get("Huidige waarde", "€ 0,00")
                    dag_raw = row.get("Dag W/V (EUR)_fmt", "€ 0,00")
                    dag_pct = row.get("Dag W/V (%)_fmt", "0,00%")
                    
                    if "-" in result_raw and "0,00" not in result_raw:
                        indicator = "🔴"
                    elif "0,00" in result_raw or result_raw.strip() == "-":
                        indicator = "⚪"
                    else:
                        indicator = "🟢"
                        
                    dag_indicator = "🔴" if "-" in dag_raw and "0,00" not in dag_raw else ("⚪" if "0,00" in dag_raw else "🟢")
                        
                    label = f"**{product_name}** — {current_val}  \n{indicator} Totaal: {result_raw} ({result_pct})  \n{dag_indicator} Dag: {dag_raw} ({dag_pct})"
                    
                    with st.expander(label):
                        c1, c2 = st.columns(2)
                        
                        c1.metric("Aantal stuks", f"{row.get('quantity', row.get('Aantal', 0)):.4g}")
                        c1.metric("Huidige Waarde", current_val)
                        
                        if 'last_price' in row:
                             c1.write(f"**Prijs p/s:** {format_eur(row['last_price'])}")
                        elif 'last_price' in cat_df.columns:
                             idx = row.name
                             if idx in cat_df.index:
                                  c1.write(f"**Prijs p/s:** {format_eur(cat_df.loc[idx, 'last_price'])}")

                        c2.metric("Totaal Geïnvesteerd", row.get("Totaal geinvesteerd", "€ 0,00"))
                        c2.metric("Totaal Resultaat", f"{result_raw} ({result_pct})")
                        c2.metric("Dag Resultaat", f"{dag_indicator} {dag_raw} ({dag_pct})")

        st.divider()

@fragment(run_every=300)
def render_rebalancing(df: pd.DataFrame, config_manager, price_manager) -> None:
    """Render de portefeuilleverdeling en rebalancing tool."""
    positions = build_positions(df)
    
    if not positions.empty:
        positions["ticker"] = positions.apply(
            lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1
        )
        
        unique_tickers = positions["ticker"].dropna().unique().tolist()
        batch_live = price_manager.get_live_prices_batch(unique_tickers)
        batch_mid = price_manager.get_midnight_prices_batch(unique_tickers)
        batch_open = price_manager.get_market_open_prices_batch(unique_tickers)
        positions["last_price"] = positions["ticker"].map(lambda t: batch_live.get(t, 0.0))
        positions["midnight_price"] = positions["ticker"].map(lambda t: batch_mid.get(t, 0.0))
        positions["market_open"] = positions["ticker"].map(lambda t: batch_open.get(t, 0.0))

        positions["current_value"] = positions.apply(
            lambda r: (
                r["quantity"] * r["last_price"]
                if pd.notna(r.get("last_price")) and pd.notna(r.get("quantity"))
                else pd.NA
            ),
            axis=1,
        )

        st.subheader("Portefeuilleverdeling & Rebalancing")
        
        saved_assets = config_manager.get_assets()
        
        with st.container(border=True):
            with st.expander("➕ Nieuw aandeel toevoegen aan verdeling"):
                col_add_1, col_add_2 = st.columns(2)
                with col_add_1:
                    new_asset_name = st.text_input("Productnaam (voor weergave)", key="new_asset_name", help="Leesbare naam, bijv. 'Vanguard World'")
                with col_add_2:
                    new_asset_key = st.text_input("Ticker / ISIN (Key)", key="new_asset_key", help="Unieke identifier, bijv. 'VWCE.DE' of 'IE00...'")
                
                new_asset_target = st.number_input("Gewenst percentage (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, key="new_asset_target")
                
                rb_settings = config_manager.get_settings()
                col_fee_1, col_fee_2 = st.columns(2)
                with col_fee_1:
                    stock_fee_eur = st.number_input("Standaard fee aandelen (€)", min_value=0.0, step=0.1, value=float(rb_settings.get("stock_fee_eur", 1.0)), help="Standaard transactiekosten per order voor aandelen (EUR)")
                with col_fee_2:
                    crypto_fee_pct = st.number_input("Standaard crypto fee (%)", min_value=0.0, step=0.01, value=float(rb_settings.get("crypto_fee_pct", 0.29)), help="Procentuele fee voor crypto (bijv. 0.29 betekent 0.29%)")
                if stock_fee_eur != rb_settings.get("stock_fee_eur") or crypto_fee_pct != rb_settings.get("crypto_fee_pct"):
                    config_manager.update_settings(stock_fee=stock_fee_eur, crypto_fee=crypto_fee_pct)

                if st.button("Voeg toe"):
                    clean_key = new_asset_key.strip() if new_asset_key else ""
                    clean_name = new_asset_name.strip() if new_asset_name else ""
                    
                    if clean_key:
                        config_manager.set_asset(clean_key, target_pct=new_asset_target, display_name=clean_name)
                        
                        saved_assets = config_manager.get_assets()

                        try:
                            resolved = price_manager.resolve_ticker(clean_key)
                            if resolved:
                                price_manager.get_live_price(resolved)
                        except:
                            pass

                        st.toast(f"{clean_key} ({clean_name or 'Geen naam'}) toegevoegd!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Voer een Ticker/ISIN in.")


        alloc = positions.copy()
        alloc["alloc_value"] = alloc["current_value"].fillna(alloc["invested"])
        alloc = alloc[alloc["alloc_value"].notna() & (alloc["alloc_value"] > 0)]
        
        total_value = alloc["alloc_value"].sum() if not alloc.empty else 0.0
        
        show_table = (total_value > 0) or bool(saved_assets)

        if show_table:
            total_value = max(total_value, 1.0)

            if not alloc.empty:
                alloc["current_pct"] = (alloc["alloc_value"] / total_value) * 100.0
                alloc["Display Name"] = alloc["product"].apply(_shorten_name)
            else:
                alloc = pd.DataFrame(columns=["Display Name", "current_pct", "alloc_value"])
            
            editor_df = alloc[["Display Name", "current_pct"]].copy()
            editor_df = editor_df.rename(columns={"Display Name": "Productnaam", "current_pct": "Huidig %"})
            editor_df["Huidig %"] = editor_df["Huidig %"].round(1)
            
            current_keys = set(alloc["product"].unique()) if "product" in alloc.columns else set()
            
            all_keys = current_keys.union(saved_assets.keys())
            
            rows = []
            for key in all_keys:
                name = config_manager.get_product_name(key)
                
                curr_pct = 0.0
                match = alloc[alloc["product"] == key]
                if not match.empty:
                    curr_pct = match.iloc[0]["current_pct"]
                
                target = 0.0
                if key in saved_assets:
                    target = float(saved_assets[key].get("target_pct", 0.0))
                
                check_val = key
                if not match.empty:
                    if "isin" in match.columns:
                        check_val = match.iloc[0]["isin"]
                
                is_crypto = str(check_val).startswith("XFC")
                sort_cat = 1 if is_crypto else 0
                
                rows.append({
                    "Productnaam": name,
                    "Ticker/ISIN": key,
                    "Huidig %": round(curr_pct, 1),
                    "Doel %": target,
                    "sort_cat": sort_cat
                })
            
            editor_df = pd.DataFrame(rows)
            
            if not editor_df.empty:
                editor_df = editor_df.sort_values(
                    by=["sort_cat", "Doel %"], 
                    ascending=[True, False]
                )
                
                editor_df.set_index("Ticker/ISIN", inplace=True)
                editor_df = editor_df[["Productnaam", "Huidig %", "Doel %"]]
            else:
                editor_df = pd.DataFrame(columns=["Productnaam", "Huidig %", "Doel %"])

            with st.form("rebalance_form"):
                st.write("Pas hieronder de gewenste verdeling aan (en pas namen aan):")
                
                st.markdown("Pas de percentages aan met de + en - knoppen. Je kunt ook de weergavenaam aanpassen.")
                
                edited_rows = []
                for idx, row in editor_df.iterrows():
                    product_label = f"📝 {row['Productnaam']}  |  H: {row['Huidig %']:.1f}%  |  D: {row['Doel %']:.1f}%"
                    
                    with st.expander(product_label):
                        c1, c2 = st.columns(2)
                        
                        with c1:
                            st.write(f"**Productnaam / Weergavenaam:**")
                            st.write(f"{row['Productnaam']}")
                            st.write("")
                            st.write(f"**Huidig Percentage:**")
                            st.write(f"{row['Huidig %']:.1f} %")
                            
                        with c2:
                            new_name = st.text_input("Naam bewerken (optioneel):", value=row["Productnaam"], key=f"name_{idx}")
                            new_target = st.number_input("Doel % instellen:", min_value=0.0, max_value=100.0, step=0.1, value=float(row["Doel %"]), key=f"target_{idx}")
                    
                        edited_rows.append({
                            "Ticker/ISIN": idx,
                            "Productnaam": new_name,
                            "Doel %": new_target
                        })
                
                edited_df = pd.DataFrame(edited_rows).set_index("Ticker/ISIN")
                
                st.markdown("---")
                with st.container(border=True):
                    st.subheader("💡 Slimme Rebalancing met Budget")
                    col_b1, col_b2 = st.columns([2, 1])
                with col_b1:
                    extra_budget = st.number_input(
                        "Nieuwe investering (€)", 
                        min_value=0.0, 
                        step=50.0, 
                        help="Voer het bedrag in dat je extra wilt investeren."
                    )
                with col_b2:
                    st.write("")
                    prevent_sell = st.checkbox("Voorkom verkoop", value=False, help="Schakel dit in om alleen bijkopen te suggereren.")
                
                    submitted = st.form_submit_button("📊 Update Berekening & Grafiek", type="primary")

            if submitted:
                updates = []
                for idx, row in edited_df.iterrows():
                    key = idx
                    new_target = float(row["Doel %"])
                    new_name = str(row["Productnaam"]).strip()
                    
                    existing_name = config_manager.get_product_name(key)
                    
                    updates.append({
                        "key": key,
                        "target_pct": new_target,
                        "display_name": new_name if (new_name and new_name != existing_name) else None
                    })
                    
                config_manager.batch_update_assets(updates)
                
                st.toast("Verdeling en namen opgeslagen!", icon="💾")

            if not editor_df.empty and "Huidig %" in editor_df.columns:
                 watchlist_items = editor_df[editor_df["Huidig %"] == 0.0].index.tolist()
            else:
                 watchlist_items = []

            if watchlist_items:
                key_to_name = editor_df["Productnaam"].to_dict()
                options = [f"{key_to_name[k]} ({k})" for k in watchlist_items]
                
                to_remove_display = st.multiselect("Verwijder nieuwe aandelen:", options)
                if st.button("Verwijder geselecteerde"):
                    keys_to_remove = []
                    for item in to_remove_display:
                        k = item.split("(")[-1].strip(")")
                        keys_to_remove.append(k)
                    config_manager.batch_remove_assets(keys_to_remove)
                    st.toast("Aandelen verwijderd!", icon="🗑️")
                    st.rerun()


            total_target = edited_df["Doel %"].sum()
            if abs(total_target - 100.0) > 0.2:
                st.warning(f"Totaal doelpercentage is {total_target:.1f}% (moet ~100% zijn).")

            new_total_value = total_value + extra_budget
            
            buy_gaps = []
            for idx, row in edited_df.iterrows():
                key = idx 
                
                match_rows = alloc[alloc["product"] == key]
                curr_val = match_rows.iloc[0]["alloc_value"] if not match_rows.empty else 0.0
                target_val = new_total_value * (row["Doel %"] / 100.0)
                gap = target_val - curr_val
                if gap > 0:
                    buy_gaps.append(gap)
            
            total_buys_needed = sum(buy_gaps)
            budget_scaling_factor = 1.0
            if prevent_sell and extra_budget > 0 and total_buys_needed > extra_budget:
                budget_scaling_factor = extra_budget / total_buys_needed

            raw_actions = []
            rb_settings = config_manager.get_settings()

            for idx, row in edited_df.iterrows():
                product_key = idx
                target_pct = row["Doel %"]
                
                display_name = row["Productnaam"]
                
                match_rows = alloc[alloc["product"] == product_key]
                if not match_rows.empty:
                    curr_row = match_rows.iloc[0]
                    curr_val = curr_row["alloc_value"]
                    last_price = curr_row.get("last_price", 0.0) 
                    if pd.isna(last_price): last_price = 0.0
                    isin = curr_row.get("isin", "")
                else:
                    curr_val = 0.0
                    isin = ""
                    resolved = price_manager.resolve_ticker(product_key)
                    last_price = price_manager.get_live_price(resolved) if resolved else 0.0
                
                target_val = new_total_value * (target_pct / 100.0)
                diff = target_val - curr_val
                if prevent_sell and diff > 0:
                    diff *= budget_scaling_factor

                if last_price > 0:
                    qty_calculated = diff / last_price
                else:
                    qty_calculated = 0.0
                
                check_str = str(product_key).upper() + " " + str(display_name).upper()
                is_crypto = any(x in check_str for x in ["BTC", "ETH", "COIN", "CRYPTO", "BITCOIN", "ETHEREUM"])
                
                if is_crypto:
                    qty_to_trade = qty_calculated
                    executed_diff = diff
                else:
                    qty_to_trade = round(qty_calculated)
                    executed_diff = qty_to_trade * last_price
                
                fee = 0.0
                if abs(qty_to_trade) > 0:
                    if is_crypto:
                        fee_pct = float(rb_settings.get("crypto_fee_pct", 0.29))
                        fee = abs(executed_diff) * (fee_pct / 100.0)
                    else:
                        fee = float(rb_settings.get("stock_fee_eur", 1.0))

                action = "Kopen" if qty_to_trade > 0 else "Verkopen"
                is_valid = True
                if (prevent_sell and qty_to_trade < 0):
                    is_valid = False
                elif (abs(executed_diff) < 1.0) or (not is_crypto and qty_to_trade == 0):
                    is_valid = False
                
                if not is_valid:
                    qty_to_trade = 0.0
                    executed_diff = 0.0
                    fee = 0.0
                    action = "-"

                raw_actions.append({
                    "Ticker/ISIN": product_key,
                    "Productnaam": display_name,
                    "Actie": action,
                    "Verschil (EUR)": executed_diff,
                    "Aantal": qty_to_trade,
                    "Kosten (Fee)": fee,
                    "curr_val": curr_val,
                    "target_val": target_val,
                    "last_price": last_price,
                    "is_crypto": is_crypto,
                    "isin": isin
                })

            def calc_net(actions):
                buys = sum(a["Verschil (EUR)"] + a["Kosten (Fee)"] for a in actions if a["Actie"] == "Kopen")
                sells = sum(abs(a["Verschil (EUR)"]) - a["Kosten (Fee)"] for a in actions if a["Actie"] == "Verkopen")
                return buys - max(0, sells)

            tolerance = extra_budget * 0.1
            current_net = calc_net(raw_actions)
            if current_net > extra_budget + tolerance:
                buys_indices = [i for i, a in enumerate(raw_actions) if a["Actie"] == "Kopen" and not a["is_crypto"]]
                buys_indices.sort(key=lambda i: raw_actions[i]["last_price"], reverse=True)
                
                for idx in buys_indices:
                    action_item = raw_actions[idx]
                    if action_item["Aantal"] >= 1:
                        action_item["Aantal"] -= 1
                        action_item["Verschil (EUR)"] = action_item["Aantal"] * action_item["last_price"]
                        if action_item["Aantal"] == 0:
                            action_item["Kosten (Fee)"] = 0.0
                            action_item["Actie"] = "-"
                        else:
                            check_str = str(action_item["Productnaam"]) + str(action_item["Ticker/ISIN"])
                            is_core = "Vanguard" in check_str or action_item["isin"] == "IE00BK5BQT80"
                            action_item["Kosten (Fee)"] = 1.0 if is_core else 3.0
                        
                        current_net = calc_net(raw_actions)
                        if current_net <= extra_budget + tolerance:
                            break

            total_executed_buys = sum(a["Verschil (EUR)"] for a in raw_actions if a["Actie"] == "Kopen")
            total_executed_sells = sum(abs(a["Verschil (EUR)"]) for a in raw_actions if a["Actie"] == "Verkopen")
            actual_new_total = total_value + total_executed_buys - total_executed_sells
            
            results = []
            for act in raw_actions:
                new_val_projected = act["curr_val"] + act["Verschil (EUR)"]
                new_pct_projected = (new_val_projected / actual_new_total) * 100.0 if actual_new_total > 0 else 0.0
                
                results.append({
                    "Ticker/ISIN": act["Ticker/ISIN"],
                    "Productnaam": act["Productnaam"], 
                    "Actie": act["Actie"],
                    "Verschil (EUR)": act["Verschil (EUR)"],
                    "Aantal": act["Aantal"],
                    "Kosten (Fee)": act["Kosten (Fee)"],
                    "Nieuw %": new_pct_projected,
                    "Huidige Waarde": act["curr_val"],
                    "Doel Waarde": act["target_val"],
                    "Planwaarde": new_val_projected
                })

            res_df = pd.DataFrame(results)
            
            st.markdown("#### Actie Advies")
            st.markdown("Dit overzicht houdt rekening met het feit dat aandelen in hele stuks gekocht worden en bevat de transactiekosten.")
            styled_res = res_df[["Productnaam", "Actie", "Verschil (EUR)", "Aantal", "Kosten (Fee)", "Nieuw %"]].style.format({
                "Verschil (EUR)": "€\xa0{:.2f}",
                "Aantal": "{:.4f}",
                "Kosten (Fee)": "€\xa0{:.2f}",
                "Nieuw %": "{:.2f}\xa0%"
            })
            if hasattr(styled_res, 'hide'):
                styled_res = styled_res.hide(axis="index")
            st.table(styled_res)

            summary_fees_buys = sum(r["Kosten (Fee)"] for r in results if r["Actie"] == "Kopen")
            summary_fees_sells = sum(r["Kosten (Fee)"] for r in results if r["Actie"] == "Verkopen")
            total_out = total_executed_buys + summary_fees_buys
            total_in = max(0, total_executed_sells - summary_fees_sells)
            net_deposit = total_out - total_in
            total_fees = summary_fees_buys + summary_fees_sells

            st.markdown("#### 💰 Financieel Overzicht")
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Totaal aankopen (incl. fees)", f"€ {total_out:.2f}")
            with col_s2:
                st.metric("Totaal verkopen (na fees)", f"€ {total_in:.2f}")
            with col_s3:
                net_deposit = total_out - total_in
                st.metric("Netto bijstorten", f"€ {max(0, net_deposit):.2f}", 
                          delta=f"Kosten: € {total_fees:.2f}", delta_color="inverse")
            
            if net_deposit > 0:
                st.info(f"💡 **Advies:** Stort exact **€ {net_deposit:.2f}** bij om dit plan uit te voeren.")
            elif net_deposit < 0:
                st.success(f"✅ **Resultaat:** Je houdt **€ {abs(net_deposit):.2f}** cash over na deze transacties.")
            
            st.markdown("#### Huidig vs Doel (Overlay)")
            
            fig = go.Figure()

            fig.add_trace(go.Pie(
                labels=res_df["Productnaam"],
                values=res_df["Doel Waarde"],
                name="Doel",
                hole=0.6,
                sort=False,
                direction='clockwise',
                showlegend=True,
                marker=dict(line=dict(color='#000000', width=2))
            ))

            fig.add_trace(go.Pie(
                labels=res_df["Productnaam"],
                values=res_df["Huidige Waarde"], 
                name="Huidig",
                hole=0, 
                domain={'x': [0.25, 0.75], 'y': [0.25, 0.75]},
                sort=False,
                direction='clockwise',
                showlegend=False,
                textinfo='label+percent',
                textposition='inside'
            ))

            fig.update_layout(
                title="Buitenring = Doel  |  Binnen = Huidig",
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=30, b=0, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
    else:
        st.caption("Geen open posities gevonden op basis van de transacties.")

def render_charts(df: pd.DataFrame, history_df: pd.DataFrame, trading_volume: pd.DataFrame, drive=None, config_manager=None, price_manager=None) -> None:
    st.markdown("---")
    tab_overview, tab_rebalance, tab_balance, tab_history, tab_pnl, tab_trader = st.tabs(
        ["📈 Overzicht", "⚖️ Rebalancing", "💰 Saldo & Cashflow", " Historie", "📊 Historische P/L", "🚀 Short Term Trader"]
    )

    with tab_overview:
        render_overview(df, config_manager=config_manager, price_manager=price_manager)

    with tab_rebalance:
        render_rebalancing(df, config_manager, price_manager)


    with tab_balance:
        st.subheader("Aandelen Gekocht vs Verkocht per maand")
        if not trading_volume.empty:
            fig_cf = px.bar(
                trading_volume, x="month_str", y="amount_abs", color="type",
                barmode="overlay", opacity=0.7,
                color_discrete_map={"Buy": "#EF553B", "Sell": "#00CC96"},
                labels={"month_str": "Maand", "amount_abs": "Bedrag (EUR)", "type": "Actie"},
            )
            fig_cf.update_layout(
                dragmode=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_cf, use_container_width=True, config={'scrollZoom': False})
        else:
            st.caption("Geen aan- of verkopen gevonden.")
    
    with tab_history:
        st.subheader("Historische waardeontwikkeling")
        
        period_options = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD", "5Y", "ALL"]
        selected_period = st.radio("Kies periode:", period_options, index=2, horizontal=True, label_visibility="collapsed")
        
        now = pd.Timestamp.now()
        start_date = None
        resample_rule = None
        
        if selected_period == "1D":
            start_date = now - pd.Timedelta(days=1)
            resample_rule = '5min'
        elif selected_period == "1W":
            start_date = now - pd.Timedelta(weeks=1)
            resample_rule = '1H'
        elif selected_period == "1M":
            start_date = now - pd.DateOffset(months=1)
            resample_rule = 'D'
        elif selected_period == "3M":
            start_date = now - pd.DateOffset(months=3)
            resample_rule = 'D'
        elif selected_period == "6M":
            start_date = now - pd.DateOffset(months=6)
            resample_rule = 'D'
        elif selected_period == "1Y":
            start_date = now - pd.DateOffset(years=1)
            resample_rule = 'D'
        elif selected_period == "5Y":
            start_date = now - pd.DateOffset(years=5)
            resample_rule = 'W-FRI'
        elif selected_period == "YTD":
            start_date = pd.Timestamp(year=now.year, month=1, day=1)
            resample_rule = 'D'
        elif selected_period == "ALL":
            start_date = None
            resample_rule = 'W-FRI'

        st.markdown(
            "Hier zie je hoeveel waarde je in bezit had (Aantal * Koers). "
            "De resolutie (uur/dag/week) past zich automatisch aan je selectie aan."
        )

        if not history_df.empty:
            products = sorted(history_df["product"].unique())
            selected_product = st.selectbox("Selecteer een product", products)
            subset = history_df[history_df["product"] == selected_product].copy()
            if not subset.empty:
                fig_hist = make_subplots(specs=[[{"secondary_y": True}]])
                
                df_chart = subset.copy()
                if "date" in df_chart.columns:
                    df_chart = df_chart.set_index("date").sort_index()

                try:
                    if df_chart.index.tz is None:
                        df_chart.index = df_chart.index.tz_localize("UTC")
                    df_chart.index = df_chart.index.tz_convert("Europe/Amsterdam")
                except:
                    pass
                
                if start_date:
                    s_date = pd.Timestamp(start_date)
                    if s_date.tz is None and df_chart.index.tz is not None:
                        s_date = s_date.tz_localize(df_chart.index.tz)
                    df_chart = df_chart[df_chart.index >= s_date]

                is_crypto = any(x in str(selected_product).upper() for x in ["BTC", "ETH", "COIN", "CRYPTO", "BITCOIN", "ETHEREUM"])
                ticker = price_manager.resolve_ticker(selected_product, None)
                if ticker and ("BTC" in ticker or "ETH" in ticker):
                    is_crypto = True

                if resample_rule:
                    if selected_period in ["1D", "1W"] and not is_crypto:
                         df_chart = df_chart.resample(resample_rule).last().dropna()
                    else:
                        df_chart = df_chart.resample(resample_rule).last().ffill()

                df_chart = df_chart.reset_index()

                xaxis_type = "date"
                x_values = df_chart["date"]
                
                if selected_period in ["1D", "1W"] and not is_crypto:
                    xaxis_type = "category"
                    x_values = df_chart["date"].dt.strftime("%d-%m %H:%M")
                
                fig_hist.add_trace(go.Scatter(x=x_values, y=df_chart["value"], name="Waarde in bezit (EUR)", mode='lines', connectgaps=True, line=dict(color="#636EFA")), secondary_y=False)
                fig_hist.add_trace(go.Scatter(x=x_values, y=df_chart["price"], name="Koers (EUR)", mode='lines', connectgaps=True, line=dict(color="#EF553B", dash='dot')), secondary_y=True)
                
                fig_hist.update_yaxes(title_text="Totale Waarde (€)", secondary_y=False, showgrid=True, autorange=True, fixedrange=False, rangemode="normal")
                fig_hist.update_yaxes(title_text="Koers per aandeel (€)", secondary_y=True, showgrid=False, autorange=True, fixedrange=False, rangemode="normal")
                
                fig_hist.update_layout(
                    title_text=f"Historie voor {selected_product}", hovermode="x unified",
                    legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255, 255, 255, 0)"),
                    xaxis=dict(
                        type=xaxis_type,
                        rangeslider=dict(visible=False),
                        nticks=10 if xaxis_type == "category" else None
                    ),
                    dragmode=False,
                    yaxis=dict(autorange=True, fixedrange=False, rangemode="normal"),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )

                fig_hist.update_yaxes(title_text="Totale Waarde (€)", secondary_y=False, showgrid=True, autorange=True, fixedrange=False, rangemode="normal")
                fig_hist.update_yaxes(title_text="Koers per aandeel (€)", secondary_y=True, showgrid=False, autorange=True, fixedrange=False, rangemode="normal")
                
                st.plotly_chart(fig_hist, use_container_width=True, config={'scrollZoom': False})
                with st.expander("Toon tabel data"):
                    st.dataframe(subset.sort_values("date", ascending=False), use_container_width=True)
            else:
                st.warning("Geen data gevonden voor dit product.")
        
        st.markdown("---")
        st.subheader("Vergelijk Portefeuille")
        st.markdown("Hieronder kun je meerdere aandelen tegelijk zien. Deselecteer de grootste posities om de dalingen/stijgingen van kleinere posities beter te zien.")
        
        if not history_df.empty and "product" in history_df.columns:
            all_products = sorted(history_df["product"].unique())
            selected_for_compare = st.multiselect("Selecteer aandelen om te vergelijken", all_products, default=all_products)
            if selected_for_compare:
                compare_df = history_df[history_df["product"].isin(selected_for_compare)].copy()
                if not compare_df.empty:
                    compare_df = compare_df.sort_values("date")
                    
                    if "date" in compare_df.columns:
                        compare_df = compare_df.set_index("date").sort_index()

                    try:
                        if compare_df.index.tz is None:
                            compare_df.index = compare_df.index.tz_localize("UTC")
                        compare_df.index = compare_df.index.tz_convert("Europe/Amsterdam")
                    except:
                        pass

                    if start_date:
                        s_date = pd.Timestamp(start_date)
                        if s_date.tz is None and compare_df.index.tz is not None:
                             s_date = s_date.tz_localize(compare_df.index.tz)
                        compare_df = compare_df[compare_df.index >= s_date]
                    
                    if resample_rule:
                         compare_df = compare_df.groupby("product").resample(resample_rule).last().ffill()
                         
                         for name in compare_df.index.names:
                             if name in compare_df.columns:
                                 compare_df = compare_df.drop(columns=[name])
                                 
                         compare_df = compare_df.reset_index()
                    else:
                        compare_df = compare_df.reset_index()

                    if "product" in compare_df.columns:
                        compare_df["product"] = compare_df["product"].apply(_shorten_name)
                    
                    # Bereken rendementspercentage ten opzichte van de investering
                    compare_df["return_pct"] = 0.0
                    mask_invested = (compare_df["invested"] != 0) & (compare_df["invested"].notna())
                    compare_df.loc[mask_invested, "return_pct"] = (
                        (compare_df.loc[mask_invested, "value"] - compare_df.loc[mask_invested, "invested"]) 
                        / compare_df.loc[mask_invested, "invested"].abs()
                    ) * 100.0

                    fig_compare = px.line(
                        compare_df, x="date", y="return_pct", color="product", 
                        title="Rendement per product in de tijd (%)", 
                        labels={"return_pct": "Rendement (%)", "date": "Datum", "product": "Product"}
                    )
                    
                    # Voeg een nullijn toe ter referentie
                    fig_compare.add_hline(y=0, line_dash="dash", line_color="rgba(255, 255, 255, 0.5)", line_width=2)
                    
                    fig_compare.update_traces(connectgaps=True)
                
                fig_compare.update_layout(
                    legend=dict(orientation="h", yanchor="top", y=-0.4, xanchor="left", x=0),
                    yaxis=dict(autorange=True, fixedrange=False, rangemode="normal"),
                    xaxis=dict(
                        type="date",
                        rangeslider=dict(visible=False)
                    ),
                    dragmode=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_compare, use_container_width=True, config={'scrollZoom': False})
            else:
                st.info("Geen data om te tonen.")
        else:
            st.info("Geen historische data beschikbaar.")
            
    with tab_pnl:
        st.subheader("Winst & Verlies Analyse")

        if history_df.empty:
            st.info("Nog onvoldoende data verzameld voor rendementsanalyse.")
        else:
            st.markdown("Kies een periode om je gerealiseerde en ongerealiseerde groei-ontwikkeling te analyseren.")
            pnl_modes = {"Dagelijks": "D", "Wekelijks": "W-MON", "Maandelijks": "ME"}
            selected_pnl_mode = st.radio("Tijdsbestek:", list(pnl_modes.keys()), horizontal=True, label_visibility="collapsed")
            res_freq = pnl_modes[selected_pnl_mode]

            # ── Stap 1: dagelijkse close en qty per product ───────────────────────
            # Pivot history_df naar dagelijkse close-prijs en qty per product.
            # Resample naar "D" zodat we één waarde per kalenderdag hebben.
            _close_pivot = (
                history_df
                .pivot_table(index="date", columns="product", values="price", aggfunc="last")
                .resample("D").last()
                .ffill()
            )
            _qty_pivot = (
                history_df
                .pivot_table(index="date", columns="product", values="quantity", aggfunc="last")
                .resample("D").last()
                .ffill()
                .fillna(0)
            )

            # ── Stap 2: dagelijkse P/L = (close - prev_close) × qty ──────────────
            # Identiek aan de logica in de metrics panel:
            #   dag_pl = (live - prev_close) × qty
            # Alleen gebruiken we hier close en prev_close uit de historische data.
            _prev_close = _close_pivot.shift(1)
            _daily_pl_per_product = (_close_pivot - _prev_close) * _qty_pivot
            _daily_pl = _daily_pl_per_product.sum(axis=1)          # totaal over alle producten
            _daily_pl = _daily_pl.iloc[1:]                          # eerste rij (geen prev) weggooien

            # ── Stap 3: overschrijf vandaag met live prijs van price_manager ──────
            # build_portfolio_history is gecached (ttl=3600). Voor vandaag gebruiken
            # we price_manager (zelfde bron als de metrics panel) zodat de laatste
            # balk altijd klopt.
            today = pd.Timestamp.now().normalize()
            if price_manager is not None:
                try:
                    _pos = build_positions(df)
                    _tracked = set(history_df["product"].dropna().unique())
                    _pos = _pos[_pos["product"].isin(_tracked)]
                    if not _pos.empty:
                        _pos["_ticker"] = _pos.apply(
                            lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1)
                        _live_px   = price_manager.get_live_prices_batch(_pos["_ticker"].dropna().unique().tolist())
                        _prev_px   = price_manager.get_prev_closes_batch(_pos["_ticker"].dropna().unique().tolist())
                        def _safe_today_pl(r):
                            tick = r.get("_ticker")
                            if not tick: return 0.0
                            lp = _live_px.get(tick, 0.0)
                            pp = _prev_px.get(tick, 0.0)
                            if lp <= 0 or pp <= 0: return 0.0
                            return r["quantity"] * (lp - pp)
                            
                        _today_pl = float(_pos.apply(_safe_today_pl, axis=1).sum())
                        if today not in _daily_pl.index:
                            _daily_pl[today] = _today_pl
                        else:
                            _daily_pl[today] = _today_pl
                        _daily_pl = _daily_pl.sort_index()
                except Exception:
                    pass

            # ── Stap 4: cumulatieve P/L = cumsum van dagelijkse P/L ───────────────
            _cum_pl = _daily_pl.cumsum()

            period_series = pd.DataFrame({
                "period_pl_eur": _daily_pl,
                "cum_pl_eur":    _cum_pl,
            })

            # Resample naar gekozen granulariteit (dag/week/maand)
            if res_freq == "D":
                period_df = period_series.copy()
            else:
                period_df = period_series.resample(res_freq).agg({
                    "period_pl_eur": "sum",    # tel dagelijkse P/L op binnen periode
                    "cum_pl_eur":    "last",   # cumulatieve P/L = laatste waarde in periode
                })
            period_df = period_df.dropna(subset=["period_pl_eur"])

            # Invested nodig voor rendements-% berekening
            tracked_products = set(history_df["product"].dropna().unique())
            tracked_df = df[df["product"].isin(tracked_products)].copy()
            global_inv = build_global_invested_history(tracked_df)

            def _lookup_invested(d):
                naive = d.tz_localize(None) if d.tzinfo is not None else d
                return global_inv.get(naive.normalize(), pd.NA)

            period_df["invested"] = pd.Series(
                [_lookup_invested(d) for d in period_df.index],
                index=period_df.index
            ).astype(object).apply(pd.to_numeric, errors="coerce").ffill().fillna(0.0)

            period_df["cum_pl_pct"] = (
                (period_df["cum_pl_eur"] / period_df["invested"].replace(0, pd.NA)) * 100.0
            ).fillna(0)

            if len(period_df) > 1:
                # Datum labels
                if selected_pnl_mode == "Maandelijks":
                    period_df["period_str"] = period_df.index.strftime("%b %Y")
                else:
                    period_df["period_str"] = period_df.index.strftime("%d-%m-%Y")

                filter_col1, filter_col2 = st.columns([1, 2])
                with filter_col1:
                    lookback_options = {"Afgelopen 30 Dagen": 30, "Afgelopen 90 Dagen": 90, "Afgelopen Jaar": 365, "Alles": 9999}
                    if selected_pnl_mode != "Dagelijks":
                        lookback_options = {"Afgelopen 6 Maanden": 180, "Afgelopen Jaar": 365, "Alles": 9999}

                    lookback_label = st.selectbox("Periode filter:", list(lookback_options.keys()))
                    days_back = lookback_options[lookback_label]

                    cutoff_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days_back)
                    display_df = period_df[
                        (period_df.index >= cutoff_date) & (period_df["invested"] > 0)
                    ].copy()

                if display_df.empty:
                    st.warning("Geen data voor deze specifieke periode.")
                else:
                    st.markdown("#### Periodieke P/L")
                    display_df["color"] = display_df["period_pl_eur"].apply(
                        lambda x: "#00CC96" if x >= 0 else "#EF553B")

                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=display_df["period_str"],
                        y=display_df["period_pl_eur"],
                        marker_color=display_df["color"],
                        name="Winst/Verlies (€)",
                        hovertemplate="%{x}<br>P/L: €%{y:.2f}<extra></extra>"
                    ))
                    fig_bar.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, b=10, l=10, r=10),
                        showlegend=False,
                        dragmode=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, config={"scrollZoom": False})

                    st.markdown("#### Cumulatieve P/L")
                    fig_cum = make_subplots(specs=[[{"secondary_y": True}]])

                    fig_cum.add_trace(go.Scatter(
                        x=display_df["period_str"],
                        y=display_df["cum_pl_eur"],
                        name="Cumulatieve P/L (€)",
                        mode="lines",
                        line=dict(color="#636EFA", width=3)
                    ), secondary_y=False)

                    fig_cum.add_trace(go.Scatter(
                        x=display_df["period_str"],
                        y=display_df["cum_pl_pct"],
                        name="Rendement (%)",
                        mode="lines",
                        line=dict(color="#FFA15A", width=3)
                    ), secondary_y=True)

                    fig_cum.add_hline(
                        y=0,
                        line_dash="dash",
                        line_color="rgba(255, 255, 255, 0.5)",
                        line_width=2,
                        secondary_y=False
                    )

                    fig_cum.update_yaxes(title_text="P/L (€)", secondary_y=False, showgrid=True)
                    fig_cum.update_yaxes(title_text="Rendement (%)", secondary_y=True, showgrid=False)
                    fig_cum.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, b=10, l=10, r=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        hovermode="x unified",
                        dragmode=False
                    )
                    st.plotly_chart(fig_cum, use_container_width=True, config={"scrollZoom": False})

                    # Resultatenoverzicht table removed per user request
                    pass

            else:
                st.info("Nog onvoldoende data verzameld voor rendementsanalyse.")

    with tab_trader:
        render_short_term_trader(df, config_manager, price_manager)

@fragment(run_every=300)
def render_short_term_trader(df: pd.DataFrame, config_manager, price_manager) -> None:
    """Render the Short Term Trading insights with Claude-inspired design and data-driven targets."""
    st.subheader("🚀 Short Term Trading Insights")
    
    positions = build_positions(df)
    if positions.empty:
        st.warning("Geen open posities gevonden om te analyseren.")
        return

    # Filter and resolve tickers
    positions["ticker"] = positions.apply(
        lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1
    )
    positions = positions.dropna(subset=["ticker"])
    if positions.empty:
        st.warning("Geen producten gevonden met een geldige ticker.")
        return

    # 1. Product Selection
    products = sorted(positions["product"].unique())
    default_idx = 0
    for i, p in enumerate(products):
        if any(x in str(p).upper() for x in ["BITCOIN", "BTC", "CRYPTO"]):
            default_idx = i
            break
    
    selected_product = st.selectbox("Selecteer aandeel:", products, index=default_idx)
    pos = positions[positions["product"] == selected_product].iloc[0]
    
    ticker = pos["ticker"]
    qty = pos["quantity"]
    avg_price = pos["invested"] / qty if qty != 0 else 0.0
    live_price = price_manager.get_live_price(ticker)
    
    # 2. Automated Data: Yearly Stats & Rebalancing Budget
    if config_manager is None or price_manager is None:
        st.error("Configuratiebeheer of Prijsbeheer is niet beschikbaar.")
        return

    @st.cache_data(ttl=3600)
    def _fetch_stats(t):
        h = price_manager.get_history(t, "1y")
        if h.empty: return None, None
        return float(h["High"].max()), float(h["Low"].min())
    
    yearly_max, yearly_min = _fetch_stats(ticker)

    # Calculate Total Portfolio exactly as in other dashboard tabs
    all_pos = build_positions(df)
    asset_val = 0.0
    for _, prow in all_pos.iterrows():
        # Try to get live value
        ptick = price_manager.resolve_ticker(prow.get("product"), prow.get("isin"))
        if ptick:
            lp = price_manager.get_live_price(ptick)
            if lp > 0:
                asset_val += prow["quantity"] * lp
                continue
        # Fallback to invested amount (same as rebalancing tab)
        asset_val += prow.get("invested", 0.0)

    # Get the exact current balance from the last CSV row (same as dashboard metrics)
    current_cash = 0.0
    if not df.empty:
        if "csv_row_id" in df.columns:
            sorted_df = df.sort_values(["value_date", "csv_row_id"], ascending=[False, True])
        else:
            sorted_df = df.sort_values("value_date", ascending=False)
        current_cash = sorted_df.iloc[0].get("balance", 0.0)
            
    total_portfolio_val = asset_val + current_cash
    
    asset_config = config_manager.get_asset(selected_product)
    target_pct = asset_config.get("target_percentage", asset_config.get("target_pct", 0.0))
    # Target value for this asset (e.g. 8% of total portfolio)
    target_val = (total_portfolio_val * target_pct) / 100
    current_asset_val = qty * live_price
    # The user wants the budget to be the target amount itself (for buyback planning),
    # not just the gap (which would be 0 if they currently hold more than the target).
    auto_budget = target_val
    
    # 3. Strategy Data Persistence
    strategy = config_manager.get_trading_strategy(selected_product)
    
    # Check if we should use live data-driven defaults
    # We use them if no strategy is saved OR if the user explicitly wants to follow the data
    # For a smoother experience, we'll calculate the 'live' defaults here:
    live_t1_sell = (yearly_max * 0.7) if yearly_max else round(avg_price * 1.15, 0)
    live_t1_buy = (yearly_min * 1.3) if yearly_min else round(avg_price * 0.85, 0)

    # Use saved strategy if available, otherwise use live defaults
    t1_sell_val = strategy.get("t1_sell", live_t1_sell)
    t1_buy_val = strategy.get("t1_buy", live_t1_buy)
    buy_budget_val = strategy.get("buy_budget", auto_budget)
    
    # 4. Layout: Metrics Row
    unreal_profit = current_asset_val - (qty * avg_price)
    unreal_pct = (live_price / avg_price - 1) * 100 if avg_price > 0 else 0.0
    # Realized Profit = Net Cashflow + (Qty * AvgPrice)
    total_realized_profit = pos["net_cashflow"] + (qty * avg_price)

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1.container(border=True):
        st.write("**Huidige waarde**")
        st.write(f"### {format_eur(current_asset_val)}")
        st.write(f"{qty:.4f} {selected_product}")
    with m2.container(border=True):
        st.write("**Ongerealiseerde winst**")
        color = "green" if unreal_profit >= 0 else "red"
        st.markdown(f"<h3 style='color:{color}'>{format_eur(unreal_profit)}</h3>", unsafe_allow_html=True)
        st.write(format_pct(unreal_pct))
    with m3.container(border=True):
        st.write("**Gerealiseerde winst**")
        color_r = "green" if total_realized_profit >= 0 else "red"
        st.markdown(f"<h3 style='color:{color_r}'>{format_eur(total_realized_profit)}</h3>", unsafe_allow_html=True)
        st.write("incl. dividenden")
    with m4.container(border=True):
        st.write("**Break-even**")
        st.write(f"### {format_eur(avg_price)}")
        st.write("gem. aankoopprijs")

    # 5. Interactive Inputs
    st.markdown("#### ⚙️ Strategie Instellingen")
    with st.expander("Pas targets en budget handmatig aan", expanded=False):
        # Show data hints (Symmetrical 30% span logic)
        st.caption(f"💡 **Data-check**: Jaarpiek (Doel 4): {format_eur(yearly_max) if yearly_max else 'Onbekend'} | Jaardal (Dip 4): {format_eur(yearly_min) if yearly_min else 'Onbekend'}")

        c1, c2, c3 = st.columns(3)
        t1_sell = c1.number_input("Eerste verkooptarget (€)", value=float(t1_sell_val), step=500.0)
        t1_buy = c2.number_input("Eerste terugkoopniveau (€)", value=float(t1_buy_val), step=500.0)
        buy_budget = c3.number_input("Handmatig budget (€)", value=float(buy_budget_val), step=100.0)
        
        if (t1_sell != t1_sell_val or t1_buy != t1_buy_val or buy_budget != buy_budget_val):
            config_manager.set_trading_strategy(selected_product, {
                "t1_sell": t1_sell,
                "t1_buy": t1_buy,
                "buy_budget": buy_budget
            })
            st.toast("Instellingen opgeslagen!", icon="💾")
            
        if st.button("🔄 Gebruik data-targets (Jaarpiek & Jaardal als NL4)"):
            config_manager.set_trading_strategy(selected_product, {
                "t1_sell": live_t1_sell,
                "t1_buy": live_t1_buy,
                "buy_budget": auto_budget
            })
            st.toast("Targets bijgewerkt naar 30% spanne op basis van live data! ✅")
            st.rerun()

    # 5.5 Shared Target Definitions (Used for Chart & Ladders)
    sell_targets = [
        {"label": "Doel 1", "price": t1_sell},
        {"label": "Doel 2", "price": t1_sell * (0.8/0.7)},
        {"label": "Doel 3", "price": t1_sell * (0.9/0.7)},
        {"label": "Doel 4", "price": t1_sell * (1.0/0.7)},
    ]
    buy_targets = [
        {"label": "Dip 1", "price": t1_buy},
        {"label": "Dip 2", "price": t1_buy * (1.2/1.3)},
        {"label": "Dip 3", "price": t1_buy * (1.1/1.3)},
        {"label": "Dip 4", "price": t1_buy * (1.0/1.3)},
    ]
    
    # 5.6 Visual Price Chart (SVG)
    render_trading_chart(live_price, avg_price, sell_targets, buy_targets, qty, selected_product, buy_budget)

    # 6. Sell Ladder
    st.markdown("#### 📊 Verkoop-ladder")
    st.caption("25% verkoper per niveau (4 doelen). Targets gebaseerd op jaarpiek.")
    
    total_potential_profit = 0
    with st.container(border=True):
        hcols = st.columns([1.5, 3.5, 1, 1.5, 1.5, 1.5])
        hcols[0].write("**Niveau**")
        hcols[1].write("**Voortgang**")
        hcols[2].write("**%**")
        hcols[3].write("**Aantal**")
        hcols[4].write("**Winst**")
        hcols[5].write("**Status**")
        st.divider()

        for target in sell_targets:
            price = target["price"]
            sell_qty_lvl = qty * 0.25
            profit = sell_qty_lvl * (price - avg_price)
            total_potential_profit += profit
            
            reached = live_price >= price
            progress = min(1.0, live_price / price) if price > 0 else 0.0
            
            cols = st.columns([1.5, 3.5, 1, 1.5, 1.5, 1.5])
            cols[0].markdown(f"**{target['label']}**<br><span style='font-size:11px; color:#666;'>{format_eur_smart(price)}</span>", unsafe_allow_html=True)
            cols[1].progress(progress)
            cols[2].write("25%")
            cols[3].write(f"{sell_qty_lvl:.4f}")
            cols[4].write(f"**{'+' if profit >= 0 else ''}{format_eur(profit)}**")
            if reached:
                cols[5].markdown("<span style='background:#EAF3DE; color:#27500A; padding:2px 8px; border-radius:4px; font-size:12px;'>Bereikt</span>", unsafe_allow_html=True)
            else:
                cols[5].markdown("<span style='background:#f0f0f0; color:#666; padding:2px 8px; border-radius:4px; font-size:12px;'>Nog niet</span>", unsafe_allow_html=True)

    # 7. Buy Ladder
    st.markdown("#### 🛒 Terugkoop-ladder")
    st.caption("Gespreid terugkopen — budget gebaseerd op rebalancing doelpercentage.")
    
    slice_budget = buy_budget / 4
    weighted_sum = 0
    total_rebound_coins = 0
    
    with st.container(border=True):
        # Header
        hcols = st.columns([1.5, 3.5, 1, 1.5, 1.5, 1.5])
        hcols[0].write("**Niveau**")
        hcols[1].write("**Voortgang**")
        hcols[2].write("**%**")
        hcols[3].write("**Kosten**")
        hcols[4].write("**Inkoop**")
        hcols[5].write("**Status**")
        st.divider()

        for target in buy_targets:
            price = target["price"]
            coins_back = slice_budget / price if price > 0 else 0
            weighted_sum += coins_back * price
            total_rebound_coins += coins_back
            
            reached = live_price <= price
            p_val = min(1.0, max(0.0, price / live_price))
            
            cols = st.columns([1.5, 3.5, 1, 1.5, 1.5, 1.5])
            cols[0].markdown(f"**{target['label']}**<br><span style='font-size:11px; color:#666;'>{format_eur_smart(price)}</span>", unsafe_allow_html=True)
            cols[1].progress(p_val)
            cols[2].write("25%")
            cols[3].write(f"{format_eur(slice_budget)}")
            cols[4].write(f"**{coins_back:.4f}**")
            if reached:
                cols[5].markdown("<span style='background:#E6F1FB; color:#0C447C; padding:2px 8px; border-radius:4px; font-size:12px;'>Bereikt</span>", unsafe_allow_html=True)
            else:
                cols[5].markdown("<span style='background:#f0f0f0; color:#666; padding:2px 8px; border-radius:4px; font-size:12px;'>Nog niet</span>", unsafe_allow_html=True)

    avg_buyback = weighted_sum / total_rebound_coins if total_rebound_coins > 0 else 0.0
    st.write(f"Gem. terugkooprijs bij volledige uitvoering: **{format_eur_smart(avg_buyback)}**")

def render_trading_chart(live_price, avg_price, sell_targets, buy_targets, amount, selected_product, buy_budget):
    """Generates a premium, modern vertical trading chart (SVG) for mobile and desktop."""
    import html
    
    def fmt_k_custom(n):
        """Custom rounding logic: <500 -> 0.10, 500-1k -> 1, 1k-10k -> 10, >10k -> 100."""
        if n < 500:
            val = round(n * 10) / 10
            return f"€{val:.2f}".replace(".", ",")
        elif n < 1000:
            val = round(n)
            return f"€{val}"
        elif n < 10000:
            val = round(n / 10) * 10
        else:
            val = round(n / 100) * 100
            
        if val >= 1000: return f"€{round(val/1000, 1) if val % 1000 != 0 else int(val/1000)}k"
        return f"€{val}"
    
    def fmt_eur_exact(n):
        return f"€{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Calculate ranges and scales
    all_prices = [live_price, avg_price] + [t["price"] for t in sell_targets] + [t["price"] for t in buy_targets]
    max_p = max(all_prices) * 1.08
    min_p = min(all_prices) * 0.92
    p_range = max_p - min_p
    
    W = 600
    H = 700
    pad_t = 50
    pad_b = 50
    chart_h = H - pad_t - pad_b
    bar_x = 260
    bar_w = 80  
    bar_mid = bar_x + (bar_w / 2)
    
    def py(price):
        return pad_t + (1 - (price - min_p) / p_range) * chart_h

    # Premium Color Palette
    color_bg = "#0E1117"
    color_sell_brand = "#00D094" # Vibrant Green
    color_buy_brand  = "#00A3FF" # Deep Blue
    color_cur_brand  = "#FF9500" # Warning Orange
    color_avg_brand  = "#94A3B8" # Slate
    color_track      = "rgba(255, 255, 255, 0.04)"
    color_track_border = "rgba(255, 255, 255, 0.1)"

    els = []

    # 1. Defs for Gradients and Filters
    els.append(f"""
    <defs>
        <linearGradient id="sellGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="{color_sell_brand}" stop-opacity="0.15"/>
            <stop offset="100%" stop-color="{color_sell_brand}" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="buyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="{color_buy_brand}" stop-opacity="0"/>
            <stop offset="100%" stop-color="{color_buy_brand}" stop-opacity="0.15"/>
        </linearGradient>
        <filter id="glow" x="-25%" y="-25%" width="150%" height="150%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
    </defs>
    """)

    # 2. Main Track (Background)
    els.append(f'<rect x="{bar_x}" y="{pad_t}" width="{bar_w}" height="{chart_h}" fill="{color_track}" stroke="{color_track_border}" stroke-width="1" rx="12"/>')

    # 3. Full-length Zone Highlights (Up to the top and bottom)
    y_mid = (py(min(t["price"] for t in sell_targets)) + py(max(t["price"] for t in buy_targets))) / 2
    
    # Sell zone (Top to mid)
    els.append(f'<rect x="{bar_x}" y="{pad_t}" width="{bar_w}" height="{y_mid - pad_t}" fill="url(#sellGrad)" rx="8"/>')
    # Buy zone (Mid to bottom)
    els.append(f'<rect x="{bar_x}" y="{y_mid}" width="{bar_w}" height="{pad_t + chart_h - y_mid}" fill="url(#buyGrad)" rx="8"/>')

    # Helper for Labels and Markers
    def draw_marker(price, color, label, subtext, side="right", is_bold=False, has_glow=False):
        y = py(price)
        glow_attr = 'filter="url(#glow)"' if has_glow else ""
        
        # Connection Line
        if side == "right":
            els.append(f'<line x1="{bar_x + bar_w}" y1="{y}" x2="{bar_x + bar_w + 10}" y2="{y}" stroke="{color}" stroke-width="1.5" opacity="0.6"/>')
            tx = bar_x + bar_w + 15
            anchor = "start"
        else:
            els.append(f'<line x1="{bar_x - 10}" y1="{y}" x2="{bar_x}" y2="{y}" stroke="{color}" stroke-width="1.5" opacity="0.6"/>')
            tx = bar_x - 15
            anchor = "end"

        # Dot on Track boundary
        els.append(f'<circle cx="{bar_x if side=="left" else bar_x+bar_w}" cy="{y}" r="4" fill="{color}" {glow_attr}/>')
        
        # Label Text
        els.append(f'<text x="{tx}" y="{y - 2}" font-size="13" font-weight="{"600" if is_bold else "500"}" fill="{color}" text-anchor="{anchor}" font-family="sans-serif">{html.escape(label)}</text>')
        els.append(f'<text x="{tx}" y="{y + 12}" font-size="11" fill="rgba(255,255,255,0.4)" text-anchor="{anchor}" font-family="sans-serif">{html.escape(subtext)}</text>')

    # 4. Sell Targets (Left Side)
    for t in sell_targets:
        profit_val = (amount * 0.25) * (t["price"] - avg_price)
        label_with_price = f"{t['label']} ({fmt_k_custom(t['price'])})"
        draw_marker(t["price"], color_sell_brand, label_with_price, f"+{fmt_eur_exact(profit_val)}", side="left")

    # 5. Buy Targets (Right Side)
    for t in buy_targets:
        cost_val = (buy_budget / 4)
        label_with_price = f"{t['label']} ({fmt_k_custom(t['price'])})"
        draw_marker(t["price"], color_buy_brand, label_with_price, f"Koop {fmt_eur_exact(cost_val)}", side="right")

    # 6. Average Price
    draw_marker(avg_price, color_avg_brand, f"Break-even ({fmt_k_custom(avg_price)})", "gem. aankoopprijs", side="left")

    # 7. Current Price (Indicator & Text) - RENDERED LAST TO STAY ON TOP
    y_cur = py(live_price)
    unreal_pct = (live_price / avg_price - 1) * 100 if avg_price > 0 else 0
    
    # Fill indicator background (Slightly brighter progress fill)
    els.append(f'<rect x="{bar_x}" y="{y_cur}" width="{bar_w}" height="{chart_h - (y_cur - pad_t)}" fill="{color_cur_brand}" opacity="0.3" rx="12"/>')
    
    # Floating Text (Above the line)
    els.append(f"""
    <text x="{bar_mid}" y="{y_cur - 6}" font-size="11" font-weight="700" fill="{color_cur_brand}" text-anchor="middle" font-family="sans-serif" filter="url(#glow)">
        {fmt_k_custom(live_price)} ({unreal_pct:+.1f}%)
    </text>
    """)
    
    # Sharp indicator lines ON TOP of the bar (Exact width, no overhang)
    els.append(f'<line x1="{bar_x}" y1="{y_cur}" x2="{bar_x+bar_w}" y2="{y_cur}" stroke="{color_cur_brand}" stroke-width="2.5" filter="url(#glow)"/>')

    svg_content = "".join(els)
    svg_full = f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" style="background:transparent; overflow:visible;">{svg_content}</svg>'
    
    st.markdown("#### 🔭 Visuele Prijsladder")
    # Wrap in a modern card
    st.markdown(
        f"""
        <div style="background:{color_bg}; border-radius:16px; padding:30px 15px; border:1px solid rgba(255,255,255,0.05); box-shadow: 0 10px 30px rgba(0,0,0,0.4); margin-bottom:20px;">
            {svg_full}
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Legend
    st.markdown(f"""
    <div style="display:flex; gap:20px; margin-top:5px; font-size:12px; color:#64748B; flex-wrap:wrap; justify-content:center; letter-spacing:0.3px;">
        <span style="display:flex;align-items:center;gap:8px;"><div style="width:10px;height:10px;background:{color_sell_brand};border-radius:2px;"></div> VERKOOP</span>
        <span style="display:flex;align-items:center;gap:8px;"><div style="width:10px;height:10px;background:{color_buy_brand};border-radius:2px;"></div> INKOOP</span>
        <span style="display:flex;align-items:center;gap:8px;"><div style="width:10px;height:10px;background:{color_cur_brand};border-radius:2px;"></div> HUIDIG</span>
        <span style="display:flex;align-items:center;gap:8px;"><div style="width:10px;height:10px;background:{color_avg_brand};border-radius:2px;"></div> BREAK-EVEN</span>
    </div>
    """, unsafe_allow_html=True)

