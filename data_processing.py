import re
import pandas as pd
import streamlit as st
import yfinance as yf
from utils import _shorten_name

@st.cache_data(show_spinner=False)
def load_degiro_csv(file_bytes: bytes) -> pd.DataFrame:
    """Load a DeGiro CSV file (Account or Transactions) into a cleaned DataFrame."""
    import io
    import math
    
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Detect if it's a Transactions export (has 'aantal' or 'quantity')
    if 'aantal' in df.columns or 'quantity' in df.columns:
        return _parse_transactions_csv(df)
    return _parse_account_csv(df)

def _clean_num(x):
    import math
    if pd.isna(x): return None
    if isinstance(x, (float, int)): return float(x) if not math.isnan(x) else None
    if not isinstance(x, str): return None
    x = x.replace("EUR", "").replace("USD", "").replace("GBP", "").strip()
    if not x or x.lower() in ("nan", "none", "-"): return None
    last_comma = x.rfind(',')
    last_dot = x.rfind('.')
    if last_comma > last_dot:
        x = x.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        x = x.replace(",", "")
    elif last_comma != -1: # Only a comma exists
        x = x.replace(",", ".")
    try:
        return float(x)
    except:
        return None

def _parse_transactions_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Parse a Transactions.csv and convert its rows to match the Account.csv schema."""
    cols = df.columns.tolist()
    def get_col(candidates):
        for c in candidates:
            if c in cols: return c
        return None
        
    c_date = get_col(['datum', 'date'])
    c_time = get_col(['tijd', 'time'])
    c_prod = get_col(['product'])
    c_isin = get_col(['isin'])
    c_qty = get_col(['aantal', 'quantity'])
    c_price = get_col(['koers', 'price'])
    c_waarde = get_col(['waarde eur', 'lokale waarde', 'value eur', 'value'])
    c_fx = get_col(['autofx kosten', 'autofx fee'])
    c_fee = get_col(['transactiekosten en/of kosten van derden eur', 'transaction costs', 'fee'])
    c_order = get_col(['order_id', 'order id'])
    
    records = []
    for idx, row in df.iterrows():
        d = str(row[c_date]) if c_date and pd.notna(row[c_date]) else ""
        t = str(row[c_time]) if c_time and pd.notna(row[c_time]) else ""
        prod = str(row[c_prod]) if c_prod and pd.notna(row[c_prod]) else ""
        isin = str(row[c_isin]) if c_isin and pd.notna(row[c_isin]) else ""
        
        uuid = ""
        if c_order and pd.notna(row[c_order]):
            uuid = str(row[c_order]).strip()
        elif 'unnamed: 17' in cols and pd.notna(row['unnamed: 17']):
            uuid = str(row['unnamed: 17']).strip()
            
        qty = _clean_num(row[c_qty]) if c_qty else 0.0
        price = _clean_num(row[c_price]) if c_price else 0.0
        waarde = _clean_num(row[c_waarde]) if c_waarde else 0.0
        
        # Crypto trades in DEGIRO often export with empty 'Aantal'. Calculate it:
        if (qty is None or qty == 0.0) and price and price > 0 and waarde and waarde != 0:
            calculated_qty = abs(waarde) / price
            # In DEGIRO, Buy = negative waarde, Sell = positive waarde
            qty = calculated_qty if waarde < 0 else -calculated_qty

        fx_fee = _clean_num(row[c_fx]) if c_fx else 0.0
        tx_fee = _clean_num(row[c_fee]) if c_fee else 0.0
        
        base_rec = {
            "date": d, "time": t, "value_date": d,
            "product": _shorten_name(prod), "isin": isin,
            "balance": 0.0, "fx": 0.0, "order_id": uuid, "csv_row_id": idx
        }
        
        # 1. Main Trade Row
        if qty and qty != 0:
            action = "Koop" if qty > 0 else "Verkoop"
            desc = f"{action} {abs(qty):g} @ {price}"
            rec = base_rec.copy()
            rec["description"] = desc
            rec["amount"] = waarde
            records.append(rec)
            
        # 2. FX Fee Row
        if fx_fee and fx_fee != 0:
            rec = base_rec.copy()
            rec["description"] = "Valutakosten"
            rec["amount"] = fx_fee
            records.append(rec)
            
        # 3. Transaction Fee Row
        if tx_fee and tx_fee != 0:
            rec = base_rec.copy()
            rec["description"] = "DEGIRO Transactiekosten"
            rec["amount"] = tx_fee
            records.append(rec)

    out = pd.DataFrame(records)
    if not out.empty:
        out["date"] = pd.to_datetime(out["date"], dayfirst=True, errors="coerce")
        out["value_date"] = pd.to_datetime(out["value_date"], dayfirst=True, errors="coerce")
    return out

def _parse_account_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Parse standard Account.csv (cash flows)."""
    rename_map = {
        "datum": "date", "date": "date",
        "tijd": "time", "time": "time",
        "valutadatum": "value_date", "value date": "value_date",
        "product": "product", "isin": "isin",
        "omschrijving": "description", "description": "description",
        "mutatie": "amount", "change": "amount", "value": "amount",
        "saldo": "balance", "balance": "balance",
        "fx": "fx", "order id": "order_id"
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "product" in df.columns:
        df["product"] = df["product"].apply(lambda x: _shorten_name(x) if pd.notna(x) and isinstance(x, str) else x)

    def _shift_if_currency(main_col: str):
        if main_col not in df.columns: return
        series = df[main_col].astype(str).str.strip()
        non_empty = [v for v in series.unique() if v not in ("", "nan", "NaN", "None", "0.0")]
        if len(non_empty) > 0 and len(non_empty) <= 3 and all(isinstance(v, str) and len(v) <= 3 and v.isalpha() for v in non_empty):
            try: idx = df.columns.get_loc(main_col)
            except KeyError: return
            for j in range(idx + 1, len(df.columns)):
                if isinstance(df.columns[j], str) and df.columns[j].startswith("unnamed"):
                    df[main_col] = df[df.columns[j]]
                    break

    _shift_if_currency("amount")
    _shift_if_currency("balance")

    unnamed = [c for c in df.columns if isinstance(c, str) and c.startswith("unnamed")]
    if unnamed: df = df.drop(columns=unnamed)

    for col in ["amount", "balance", "fx"]:
        if col in df.columns:
            df[col] = df[col].apply(_clean_num)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    for col in ["date", "value_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    if "csv_row_id" not in df.columns:
        df["csv_row_id"] = df.index

    return df


def classify_row(description: str) -> str:
    """Zet de omschrijving om in een transaction type."""
    desc = str(description or "").strip()

    if "Koop " in desc or desc.startswith("Buy "):
        return "Buy"
    if "Verkoop " in desc or desc.startswith("Sell "):
        return "Sell"

    if "DEGIRO Transactiekosten" in desc or "Brokerskosten" in desc or "Transaction Fee" in desc:
        return "Fee"
    if "Kosten van derden" in desc or "Third party" in desc:
        return "Fee"
    if "Aansluitingskosten" in desc or "Connectivity Fee" in desc:
        return "Fee"
    if "Valutakosten" in desc or "Auto FX" in desc:
        return "Fee"
            
    if "Dividendbelasting" in desc or "Withholding Tax" in desc:
        return "Dividend Tax"
    if "Dividend" in desc:
        return "Dividend"
    if "Flatex Interest" in desc or "Rente" in desc or "Interest" in desc:
        return "Interest"
    if "iDEAL Deposit" in desc or desc == "Deposit":
        return "Deposit"
    if "Reservation iDEAL" in desc:
        return "Reservation"
    if "Overboeking van uw geldrekening" in desc or "Storting" in desc or "Deposit" in desc:
        return "Deposit"
    if "Overboeking naar uw geldrekening" in desc or "Terugstorting" in desc or "Withdrawal" in desc:
        return "Withdrawal"
    if "Degiro Cash Sweep Transfer" in desc:
        return "Cash Sweep"

    return "Other"

def parse_quantity(description: str) -> float:
    """
    Parseer het aantal stuks uit een omschrijving zoals:
    'Koop 6 @ 146,92 EUR' of 'Verkoop 1 @ 6,75 EUR'.
    English: 'Buy 6 @ 146.92 EUR' or 'Sell 1 @ 6.75 EUR'
    """
    if not isinstance(description, str):
        return 0.0

    match = re.search(r"(Koop|Verkoop|Buy|Sell)\s+([0-9.,]+)\s+@", description)
    if not match:
        return 0.0

    action = match.group(1)
    qty_str = match.group(2).replace(".", "").replace(",", ".")

    try:
        qty = float(qty_str)
    except ValueError:
        return 0.0

    if action in ("Verkoop", "Sell"):
        qty = -qty
    return qty

@st.cache_data
def enrich_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg extra kolommen toe: type, quantity, categorieën."""
    df = df.copy()

    # --- ENRICH TIMESTAMP (Date + Time) ---
    if "date" in df.columns and "time" in df.columns:
        try:
             # Ensure date is string YYYY-MM-DD
            if pd.api.types.is_datetime64_any_dtype(df["date"]):
                 d_str = df["date"].dt.strftime("%Y-%m-%d")
            else:
                 d_str = df["date"].astype(str).str.split(" ").str[0]

            t_str = df["time"].astype(str)
            
            # Combine
            full_dt = pd.to_datetime(d_str + " " + t_str, errors="coerce")
            
            # Update value_date where successful
            if "value_date" in df.columns:
                df["value_date"] = full_dt.fillna(df["value_date"])
            else:
                df["value_date"] = full_dt
                
        except Exception:
            pass

    df["type"] = df.get("description", "").apply(classify_row)
    df["quantity"] = df.get("description", "").apply(parse_quantity)

    # Handige deelkolommen
    df["is_trade"] = df["type"].isin(["Buy", "Sell"])
    df["is_fee"] = df["type"] == "Fee"
    df["is_dividend"] = df["type"] == "Dividend"
    df["is_tax"] = df["type"] == "Dividend Tax"
    df["is_cashflow"] = df["type"].isin(
        ["Deposit", "Withdrawal", "Interest", "Cash Sweep"]
    )

    # Cashflow-deelkolommen
    df["buy_cash"] = df.apply(
        lambda r: r["amount"] if r["type"] == "Buy" else 0.0, axis=1
    )
    df["sell_cash"] = df.apply(
        lambda r: r["amount"] if r["type"] == "Sell" else 0.0, axis=1
    )

    return df

def build_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Bepaal open posities en historische cashflow per product."""
    if "product" not in df.columns:
        return pd.DataFrame()

    product_rows = df[df["product"].notna() & (df["product"] != "")].copy()
    if product_rows.empty:
        return pd.DataFrame()

    grouped = (
        product_rows.groupby(["product", "isin"], dropna=False)
        .agg(
            quantity=("quantity", "sum"),
            invested=("buy_cash", lambda s: -s.sum()),
            total_sells=("sell_cash", "sum"),
            total_fees=("amount", lambda s: s[product_rows.loc[s.index, "is_fee"]].sum()),
            total_dividends=("amount", lambda s: s[product_rows.loc[s.index, "is_dividend"]].sum()),
            total_div_tax=("amount", lambda s: s[product_rows.loc[s.index, "is_tax"]].sum()),
            net_cashflow=("amount", "sum"),
            trades=("is_trade", "sum"),
        )
        .reset_index()
    )

    grouped = grouped[grouped["quantity"] > 0]
    grouped = grouped.sort_values("invested", ascending=False)

    return grouped

def build_trading_volume_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Handelsvolume (Koop/Verkoop) per maand."""
    if "value_date" not in df.columns:
        return pd.DataFrame()

    valid = df[df["type"].isin(["Buy", "Sell"])].copy()
    if valid.empty:
        return pd.DataFrame()

    valid["month"] = valid["value_date"].dt.to_period("M").dt.to_timestamp()
    
    grouped = valid.groupby(["month", "type"])["amount"].sum()
    
    unique_months = valid["month"].unique()
    idx = pd.MultiIndex.from_product(
        [unique_months, ["Buy", "Sell"]], 
        names=["month", "type"]
    )
    
    monthly = grouped.reindex(idx, fill_value=0).reset_index()
    monthly = monthly.sort_values("month")
    
    monthly["amount_abs"] = monthly["amount"].abs()
    
    monthly["month_str"] = monthly["month"].dt.strftime("%b %Y")
    
    return monthly

@st.cache_data(ttl=3600)
def build_portfolio_history(df: pd.DataFrame, product_map: dict) -> pd.DataFrame:
    """
    Reconstrueer historische portefeuillewaarde per week.
    Combineert transacties (hoeveelheid) met historische koersen (yfinance).
    """
    if df.empty or "value_date" not in df.columns:
        return pd.DataFrame()

    products = df["product"].unique()
    valid_products = []
    
    for p in products:
        if not p: continue
        if p in product_map and product_map[p]:
            valid_products.append(p)

    if not valid_products:
        return pd.DataFrame()

    history_frames = []
    
    mask = df["type"].isin(["Buy", "Sell"]) & df["product"].isin(valid_products)
    relevant_tx = df[mask].copy()
    
    relevant_tx = relevant_tx.dropna(subset=["value_date"])

    if relevant_tx.empty:
        return pd.DataFrame()

    five_years_ago = (pd.Timestamp.now() - pd.DateOffset(years=5)).normalize()
    # Use the actual first transaction date to avoid downloading years of empty data
    first_tx_date = relevant_tx["value_date"].min().normalize()
    start_date = max(five_years_ago, first_tx_date - pd.Timedelta(days=30))
    start_date_str = start_date.strftime("%Y-%m-%d")

    unique_tickers = list(set(product_map.values()))
    try:
        yf_data = yf.download(unique_tickers, start=start_date_str, interval="1d", group_by="ticker", progress=False, threads=False)
        
        start_hourly = (pd.Timestamp.now() - pd.Timedelta(days=8)).strftime("%Y-%m-%d")
        yf_data_hourly = yf.download(unique_tickers, start=start_hourly, interval="5m", group_by="ticker", prepost=False, progress=False, threads=False)
        
    except Exception as e:
        st.error(f"Fout bij ophalen historische data: {e}")
        return pd.DataFrame()

    for p in valid_products:
        ticker = product_map[p]
        
        tx_p = relevant_tx[relevant_tx["product"] == p].copy()
        if tx_p.empty:
            continue
            
        # Net cashflow for this transaction row: negative means money left the account (invested), positive means money returned.
        tx_p["net_cashflow"] = (
            tx_p["buy_cash"] 
            + tx_p["sell_cash"]
            + tx_p.apply(lambda r: r["amount"] if r["is_fee"] else 0.0, axis=1)
            + tx_p.apply(lambda r: r["amount"] if r["is_dividend"] else 0.0, axis=1)
        )
        
        # Group by date to get daily changes
        tx_daily = tx_p.groupby("value_date").agg(
            quantity=("quantity", "sum"),
            invested_change=("net_cashflow", lambda s: -s.sum()) # Invert because negative cashflow = positive investment
        ).sort_index()

        qty_on_tx = tx_daily["quantity"].cumsum()
        invested_on_tx = tx_daily["invested_change"].cumsum()
        
        now = pd.Timestamp.now()
        full_daily_index = pd.date_range(start=start_date, end=now, freq="D")
        
        combined_index = qty_on_tx.index.union(full_daily_index).sort_values()
        
        daily_qty = qty_on_tx.reindex(combined_index, method='ffill').fillna(0)
        daily_invested = invested_on_tx.reindex(combined_index, method='ffill').fillna(0)
        
        def get_price_series(data_obj, t):
            try:
                if isinstance(data_obj.columns, pd.MultiIndex):
                    if t in data_obj.columns.levels[0]:
                        return data_obj[t]["Close"]
                if "Close" in data_obj.columns:
                     return data_obj["Close"]
            except:
                pass
            return pd.Series(dtype=float)

        price_series_daily = get_price_series(yf_data, ticker)
        price_series_hourly = get_price_series(yf_data_hourly, ticker)

        if price_series_daily.empty and price_series_hourly.empty:
            continue
            
        if price_series_daily.index.tz is not None:
             price_series_daily.index = price_series_daily.index.tz_localize(None)
        # Place the daily close at 21:30 UTC instead of midnight (00:00 UTC).
        # Problem with midnight: it is start-of-day, so intra-day transactions
        # (e.g. a sell at 09:41 CET = 08:41 UTC) are NOT yet in the cumsum → wrong value.
        # 21:30 UTC is chosen because:
        #   - After all European market closes (~16:30 UTC)
        #   - After NYSE close (21:00 UTC winter / 20:00 UTC summer)
        #   - Before Amsterdam midnight in BOTH winter (22:30 CET) AND summer (23:30 CEST)
        #     → daily close stays in the correct Amsterdam-day bucket for the resample.
        #   - 23:59:59 UTC was tried before but = 00:59:59 AMS → wrong bucket.
        price_series_daily.index = price_series_daily.index.normalize() + pd.Timedelta(hours=21, minutes=30)

        if not price_series_hourly.empty:
             if price_series_hourly.index.tz is not None:
                price_series_hourly.index = price_series_hourly.index.tz_localize(None)

        cutoff = pd.Timestamp.now() - pd.Timedelta(days=8)
        
        part1 = price_series_daily[price_series_daily.index < cutoff]
        part2 = price_series_hourly
        
        full_price_series = pd.concat([part1, part2]).sort_index()
        full_price_series = full_price_series[~full_price_series.index.duplicated(keep='last')]
        # Safeguard: remove any zero or negative prices which cause P/L spikes
        full_price_series = full_price_series[full_price_series > 0]
             
        hist_df = full_price_series.to_frame(name="price")
        
        if daily_qty.index.tz is not None:
            daily_qty.index = daily_qty.index.tz_localize(None)
        
        if hist_df.index.tz is not None:
            hist_df.index = hist_df.index.tz_localize(None)

        # 1. Determine if this product is crypto (trades 24/7) or a regular stock/ETF.
        #    For stocks: use business-day anchors only (Mon-Fri) so that weekend midnight
        #    timestamps are never injected.  Those phantom weekend points were the root
        #    cause of the P/L spikes: on Sat/Sun every product shared the same midnight
        #    anchor → ttl_history showed a *complete* portfolio sum, while on Friday only
        #    the products with the very latest 5-min tick contributed → partial sum →
        #    artificial delta on the weekend transition.
        #    For crypto: keep daily (all-day) anchors because those markets never close.
        p_isin_series = df.loc[df["product"] == p, "isin"]
        p_isin = str(p_isin_series.iloc[0]).strip() if not p_isin_series.empty and pd.notna(p_isin_series.iloc[0]) else ""
        is_crypto_product = p_isin.startswith("XFC")

        if is_crypto_product:
            daily_idx = pd.date_range(start=start_date, end=now, freq="D")
        else:
            # Business days only – no Saturday/Sunday midnight anchors
            daily_idx = pd.bdate_range(start=start_date, end=now)

        # 2. Combine the daily anchors with the high-resolution price data.
        #    The 5-min ticks from hist_df are still fully preserved here.
        final_idx = daily_idx.union(hist_df.index).sort_values()
        
        # 3. Reindex quantities and invested forward onto this new combined high-res timeline.
        #    daily_qty was built against a full-daily (all 7 days) index so it correctly
        #    carries positions across weekends; reindexing onto final_idx (which skips
        #    weekends for non-crypto) simply doesn't request those weekend rows.
        combined_qty = daily_qty.reindex(final_idx, method='ffill').fillna(0)
        combined_inv = daily_invested.reindex(final_idx, method='ffill').fillna(0)
        
        # 4. Reindex prices forward onto the combined timeline.
        combined_price = hist_df.reindex(final_idx, method='ffill')
        
        # 5. Combine into final continuous frame
        combined_df = pd.DataFrame(index=final_idx)
        combined_df["price"] = combined_price["price"]
        
        combined_df["quantity"] = combined_qty
        combined_df["invested"] = combined_inv
        
        combined_df["product"] = p
        combined_df["ticker"] = ticker
        
        combined_df["value"] = combined_df["quantity"] * combined_df["price"]
        
        combined_df = combined_df.dropna(subset=["price"])
        
        if not combined_df.empty:
            history_frames.append(combined_df)

    if not history_frames:
        return pd.DataFrame()
        
    final_df = pd.concat(history_frames)
    final_df.index.name = "date"
    return final_df.reset_index()

@st.cache_data(ttl=3600)
def build_global_invested_history(df: pd.DataFrame) -> pd.Series:
    """
    Bereken de cumulatieve 'invested' lijn over de tijd, op EXAACT dezelfde
    wijze als de '-62 P/L' op het dashboard berekend wordt.
    Dit houdt rekening met álle kosten (buy, fee) minus álle opbrengsten (sell, dividend),
    inclusief aandelen die nu niet meer in portfolio zitten.
    """
    if df.empty or "value_date" not in df.columns:
        return pd.Series(dtype=float)
        
    # We want to match: total_costs = abs(buys) + fees - abs(sells) - dividends
    cost_flow = pd.Series(0.0, index=df.index)
    
    cost_flow.loc[df["type"] == "Buy"] = df.loc[df["type"] == "Buy", "amount"].abs()
    cost_flow.loc[df["is_fee"]] = df.loc[df["is_fee"], "amount"].abs() # usually amount is negative
    cost_flow.loc[df["type"] == "Sell"] = -df.loc[df["type"] == "Sell", "amount"].abs()
    cost_flow.loc[df["is_dividend"]] = -df.loc[df["is_dividend"], "amount"].abs() # dividends reduce invested cash
    
    # Give the frame the proper dates (normalized to day)
    temp_df = pd.DataFrame({
        "date": df["value_date"].dt.normalize(),
        "cost_flow": cost_flow
    }).dropna(subset=["date"])
    
    if temp_df.empty:
        return pd.Series(dtype=float)
        
    # Group by day to get the daily net cost injection
    daily_cost_flows = temp_df.groupby("date")["cost_flow"].sum().sort_index()
    
    # Cumulative Sum to get the running total
    cumulative_invested = daily_cost_flows.cumsum()
    
    # Forward-fill to a continuous daily index up to today
    start_date = cumulative_invested.index.min()
    now = pd.Timestamp.now().normalize()
    if pd.isna(start_date):
        return pd.Series(dtype=float)
        
    daily_idx = pd.date_range(start=start_date, end=now, freq="D")
    
    # Reindex and forward fill to carry over historical invested values dynamically
    continuous_invested = cumulative_invested.reindex(daily_idx, method='ffill').fillna(0.0)
    
    return continuous_invested
