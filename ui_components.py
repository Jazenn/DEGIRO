import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import format_eur, format_pct, _shorten_name, fragment
from data_processing import build_positions

@fragment(run_every=30)
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
                base = r.get("market_open")
                
            if pd.isna(base) or base == 0:
                base = r.get("prev_close")
            
            if pd.notna(base) and base > 0:
                return qty * base
            return pd.NA

        positions["daily_base_val"] = positions.apply(calc_daily_base, axis=1)
        total_daily_base = positions["daily_base_val"].dropna().sum() if not positions.empty else 0.0

        def calc_daily(r):
            lp = r.get("last_price")
            qty = r.get("quantity")
            if pd.isna(lp) or pd.isna(qty): return pd.NA
            
            base_val = r.get("daily_base_val")
            if pd.notna(base_val) and base_val > 0:
                return (lp * qty) - base_val
            return pd.NA

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
        st.markdown(f"**Periode data:** {period_str}")
    
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
        st.metric("Dag W/V", format_eur(total_daily_pl) if pd.notna(total_daily_pl) else "€ 0,00", delta=format_pct(daily_pct_total) if pd.notna(total_daily_pl) else None, delta_color=daily_color, help="Dagelijks resultaat gebaseerd op de marktopening (of middernacht voor crypto).")
    
    col4, col5 = st.columns(2)
    with col4.container(border=True):
        st.metric("Vrije Ruimte (Saldo)", format_eur(current_balance), help="Het laatst bekende saldo uit de transactiehistorie.")
    with col5.container(border=True):
        st.metric("Ontvangen dividend", format_eur(total_dividends))
        
    st.divider()

@fragment(run_every=30)
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
                        base = row.get("market_open")
                        
                    if pd.isna(base) or base == 0:
                        base = row.get("prev_close")
                        
                    if pd.notna(base) and base > 0:
                        pl_eur = qty * (lp - base)
                        base_val = qty * base
                        pl_pct = (pl_eur / base_val * 100.0) if base_val > 0 else 0.0
                        return pl_eur, pl_pct
                    return pd.NA, pd.NA
                    
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
                        
                    label = f"{indicator} **{product_name}** | {current_val} | Tot: {result_raw} | Dag: {dag_indicator} {dag_raw} ({dag_pct})"
                    
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
                
                # Gebruik st.columns in plaats van st.data_editor om de verspringingsbug op mobiel compleet op te heffen.
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
    tab_overview, tab_balance, tab_history, tab_transactions = st.tabs(
        ["📈 Overzicht", "💰 Saldo & Cashflow", " Historie", "📋 Transacties"]
    )

    with tab_overview:
        render_overview(df, config_manager=config_manager, price_manager=price_manager)


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
                    
                    fig_compare = px.line(
                        compare_df, x="date", y="value", color="product", 
                        title="Waarde per aandeel in de tijd (EUR)", 
                        labels={"value": "Waarde (EUR)", "date": "Datum", "product": "Product"}
                    )
                    
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
            
    with tab_transactions:
        st.subheader("Ruwe transactiedata")
        st.dataframe(df, use_container_width=True, height=500)
