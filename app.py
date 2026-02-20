import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
import yfinance as yf
from drive_utils import DriveStorage
import json
from drive_utils import DriveStorage
# New modular imports (phases of refactor)
# New modular imports (managers.py)
try:
    from managers import ConfigManager, PriceManager
except ImportError:
    st.error("Essential modules missing! (managers.py)")

# Compatibility check for st.fragment (Streamlit 1.37+)
if hasattr(st, "fragment"):
    fragment = st.fragment
else:
    # Dummy decorator if getting older version
    def fragment(*args, **kwargs):
        def wrapper(f): return f
        return wrapper


def _shorten_name(name):
    """Verkort de namen van ETFs voor betere leesbaarheid op mobiel."""
    n = str(name).upper()
    if "VANGUARD" in n: return "VANGUARD"
    if "FUTURE OF DEFENCE" in n or "HANETF" in n: return "FOD"
    return name


def format_eur(value: float) -> str:
    """Format a float as European-style euro string."""
    if pd.isna(value):
        return "€ 0,00"
    # First format with US/UK style, then swap separators
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"


def format_pct(value: float) -> str:
    """Format a float as percentage with European decimal separator."""
    if pd.isna(value):
        return ""
    s = f"{value:+.2f}"  # bijv. +12.34 of -5.67
    s = s.replace(",", "X").replace(".", ",").replace("X", ",")
    return f"{s}%"


def is_tradegate_open() -> bool:
    """Check if TradeGate is open (09:00-22:00 CET, Mon-Fri)."""
    now = pd.Timestamp.now(tz='Europe/Amsterdam')
    # Only weekdays (Mon=0, Fri=4)
    if now.weekday() > 4:
        return False
    # Trading hours: 09:00 to 22:00
    hour = now.hour
    return 9 <= hour < 22


@st.cache_data
def load_degiro_csv(file) -> pd.DataFrame:
    """Load a DeGiro CSV file into a cleaned DataFrame."""
    df = pd.read_csv(file)

    # Normalise column names (strip whitespace, consistent casing)
    df.columns = [c.strip() for c in df.columns]

    # Map Dutch export columns to easier internal names
    rename_map = {
        "Datum": "date",
        "Tijd": "time",
        "Valutadatum": "value_date",
        "Product": "product",
        "ISIN": "isin",
        "Omschrijving": "description",
        "Mutatie": "amount",
        "Saldo": "balance",
        "FX": "fx",
        "Order Id": "order_id",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # In de DeGiro-export staat in de kolom 'Mutatie' / 'Saldo' meestal de valuta (EUR)
    # en staat het echte bedrag in de naastliggende 'Unnamed: x' kolom.
    # Herken dat patroon en verschuif de waarden naar 'amount' / 'balance'.

    def _shift_if_currency(main_col: str) -> None:
        if main_col not in df.columns:
            return
        series = df[main_col].astype(str).str.strip()
        non_empty = series[series != ""].unique()
        if (
            len(non_empty) > 0
            and len(non_empty) <= 3
            and all(len(v) <= 3 and v.isalpha() for v in non_empty)
        ):
            try:
                idx = df.columns.get_loc(main_col)
            except KeyError:
                return
            replacement = None
            for j in range(idx + 1, len(df.columns)):
                colname = df.columns[j]
                if isinstance(colname, str) and colname.startswith("Unnamed"):
                    replacement = colname
                    break
            if replacement is not None:
                df[main_col] = df[replacement]

    _shift_if_currency("amount")
    _shift_if_currency("balance")

    # Clean and convert numeric columns (EU format: 1.234,56 -> 1234.56)
    for col in ["amount", "balance", "fx"]:
        if col in df.columns:
            # Handle string conversion robustly
            def clean_num(x):
                if isinstance(x, str):
                    # Remove thousands separator (.), replace decimal (,)
                    # Handle common cases like 'EUR 1.250,50' or '1.000,00'
                    x = x.replace("EUR", "").replace("USD", "").strip()
                    x = x.replace(".", "").replace(",", ".")
                return x

            df[col] = df[col].apply(clean_num)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Parse dates flexibly (European %d-%m-%Y OR ISO %Y-%m-%d)
    # This prevents date loss when loading back from CSV
    for col in ["date", "value_date"]:
        if col in df.columns:
            # First try dayfirst for DeGiro native exports
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return df


def classify_row(description: str) -> str:
    """Zet de omschrijving om in een transaction type."""
    desc = str(description or "").strip()

    if "Koop " in desc:
        return "Buy"
    if "Verkoop " in desc:
        return "Sell"

    # Fees & Costs (Strict matching as requested)
    if "DEGIRO Transactiekosten" in desc or "Brokerskosten" in desc:
        return "Fee"
    if "Kosten van derden" in desc:  # Explicitly requested
        return "Fee"
    if "Aansluitingskosten" in desc or "Connectivity Fee" in desc:
        return "Fee"
    if "Valutakosten" in desc or "Auto FX" in desc:
        return "Fee"
            
    if "Dividendbelasting" in desc:
        return "Dividend Tax"
    if "Dividend" in desc:
        return "Dividend"
    if "Flatex Interest" in desc or "Rente" in desc:
        return "Interest"
    if "iDEAL Deposit" in desc:
        return "Deposit"
    if "Reservation iDEAL" in desc:
        return "Reservation"
    if "Overboeking van uw geldrekening" in desc or "Storting" in desc:
        return "Deposit"
    if "Overboeking naar uw geldrekening" in desc or "Terugstorting" in desc:
        return "Withdrawal"
    if "Degiro Cash Sweep Transfer" in desc:
        return "Cash Sweep"

    return "Other"


def parse_quantity(description: str) -> float:
    """
    Parseer het aantal stuks uit een omschrijving zoals:
    'Koop 6 @ 146,92 EUR' of 'Verkoop 1 @ 6,75 EUR'.
    """
    if not isinstance(description, str):
        return 0.0

    match = re.search(r"(Koop|Verkoop)\s+([0-9.,]+)\s+@", description)
    if not match:
        return 0.0

    action = match.group(1)
    qty_str = match.group(2).replace(".", "").replace(",", ".")
    try:
        qty = float(qty_str)
    except ValueError:
        return 0.0

    if action == "Verkoop":
        qty = -qty
    return qty



def enrich_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg extra kolommen toe: type, quantity, categorieën."""
    df = df.copy()

    # --- ENRICH TIMESTAMP (Date + Time) ---
    # Apply here so it works for BOTH new uploads AND loaded history (df_drive)
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

    # Filter op rijen die aan een product gekoppeld zijn
    # (dus trades, dividends, fees, etc. voor een specifiek aandeel)
    product_rows = df[df["product"].notna() & (df["product"] != "")].copy()
    if product_rows.empty:
        return pd.DataFrame()

    # Groepeer per product/ISIN
    grouped = (
        product_rows.groupby(["product", "isin"], dropna=False)
        .agg(
            quantity=("quantity", "sum"),
            invested=("buy_cash", lambda s: -s.sum()),  # Bruto aankoopwaarde (Positive)
            total_sells=("sell_cash", "sum"),           # Bruto verkoopwaarde (Positive)
            total_fees=("amount", lambda s: s[product_rows.loc[s.index, "is_fee"]].sum()),
            total_dividends=("amount", lambda s: s[product_rows.loc[s.index, "is_dividend"]].sum()),
            total_div_tax=("amount", lambda s: s[product_rows.loc[s.index, "is_tax"]].sum()),
            net_cashflow=("amount", "sum"),  # Som van buys(-), sells(+), fees(-), div(+), tax(-)
            trades=("is_trade", "sum"),
        )
        .reset_index()
    )

    # Alleen nog posities met resterende stukken tonen (positieve hoeveelheid)
    # Of wil je ook gesloten posities met winst/verlies zien?
    # Voor 'Overzicht' is open posities het meest logisch.
    grouped = grouped[grouped["quantity"] > 0]
    grouped = grouped.sort_values("invested", ascending=False)

    return grouped


def build_trading_volume_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Handelsvolume (Koop/Verkoop) per maand."""
    if "value_date" not in df.columns:
        return pd.DataFrame()

    # Filter alleen op Koop en Verkoop acties
    valid = df[df["type"].isin(["Buy", "Sell"])].copy()
    if valid.empty:
        return pd.DataFrame()

    valid["month"] = valid["value_date"].dt.to_period("M").dt.to_timestamp()
    
    grouped = valid.groupby(["month", "type"])["amount"].sum()
    
    # Zorg voor volledige dekkking per maand voor Buy en Sell
    unique_months = valid["month"].unique()
    idx = pd.MultiIndex.from_product(
        [unique_months, ["Buy", "Sell"]], 
        names=["month", "type"]
    )
    
    monthly = grouped.reindex(idx, fill_value=0).reset_index()
    monthly = monthly.sort_values("month")
    
    # Absolute bedragen voor visualisatie
    monthly["amount_abs"] = monthly["amount"].abs()
    
    # Categorical x-axis label
    monthly["month_str"] = monthly["month"].dt.strftime("%b %Y")
    
    return monthly


# @st.cache_data(ttl=3600)
def build_portfolio_history(df: pd.DataFrame, price_manager) -> pd.DataFrame:
    """
    Reconstrueer historische portefeuillewaarde per week.
    Combineert transacties (hoeveelheid) met historische koersen (yfinance).
    """
    if df.empty or "value_date" not in df.columns:
        return pd.DataFrame()

    # 1. Bepaal welke producten we kunnen volgen (hebben een ticker)
    #    We gebruiken de unieke producten uit de transacties.
    products = df["product"].unique()
    valid_products = []
    
    # Maak een mapping: product -> ticker
    product_map = {}
    for p in products:
        if not p: continue
        # Zoek isin erbij
        isin_series = df.loc[df["product"] == p, "isin"]
        isin_val = isin_series.iloc[0] if not isin_series.empty else None
        isin = str(isin_val).strip() if isin_val and pd.notna(isin_val) else None
        
        ticker = price_manager.resolve_ticker(p, isin)
        if ticker:
            product_map[p] = ticker
            valid_products.append(p)

    if not valid_products:
        return pd.DataFrame()

    # 2. Bouw per product de cumulatieve hoeveelheid op in de tijd
    #    We doen dit op dagbasis en resamplen later naar week.
    history_frames = []
    
    # Filter op relevante transacties
    mask = df["type"].isin(["Buy", "Sell"]) & df["product"].isin(valid_products)
    relevant_tx = df[mask].copy()
    
    # Drop rows where value_date is NaT (invalid date)
    relevant_tx = relevant_tx.dropna(subset=["value_date"])

    if relevant_tx.empty:
        return pd.DataFrame()

    # Bepaal startdatum voor download.
    # We halen nu altijd data vanaf 5 jaar geleden op, zodat de prijsgrafiek ook
    # zichtbaar is in periodes dat de gebruiker het aandeel nog niet bezat.
    # CRITICAAL: normalize() gebruiken zodat we op 00:00:00 uitkomen, anders matcht de index 
    # later niet met de normalized price data.
    start_date = (pd.Timestamp.now() - pd.DateOffset(years=5)).normalize()
    start_date_str = start_date.strftime("%Y-%m-%d")

    # Download data voor alle tickers in 1 keer (efficiënter)
    unique_tickers = list(set(product_map.values()))
    try:
        # Download DAGELIJKSE data (was wekelijks)
        yf_data = yf.download(unique_tickers, start=start_date_str, interval="1d", group_by="ticker", progress=False, threads=False)
        
        # Download HOURLY/INTRADAY data voor de laatste 8 dagen
        # period="5d" is te kort voor een volledige week view (7 dagen).
        # We gebruiken start=... om expliciet 8 dagen terug te gaan.
        start_hourly = (pd.Timestamp.now() - pd.Timedelta(days=8)).strftime("%Y-%m-%d")
        yf_data_hourly = yf.download(unique_tickers, start=start_hourly, interval="5m", group_by="ticker", progress=False, threads=False)
        
    except Exception as e:
        st.error(f"Fout bij ophalen historische data: {e}")
        return pd.DataFrame()

    # Verwerk per product
    for p in valid_products:
        ticker = product_map[p]
        
        tx_p = relevant_tx[relevant_tx["product"] == p].copy()
        if tx_p.empty:
            continue
            
        # Zet datum index.
        # LET OP: Als er meerdere transacties op exact hetzelfde moment zijn,
        # moeten we die sommeren, anders krijgen we duplicate index errors bij reindex().
        tx_p = tx_p.groupby("value_date")["quantity"].sum().sort_index()
        
        # Resample naar dag om gaten te vullen, daarna cumsum
        # FIX: Resample("D") vernietigt de tijdcomponent (zet alles op 00:00).
        # We willen de exacte tijd van transactie behouden voor intraday charts.
        # Maar we hebben OOK een dagelijks rooster nodig voor de periodes tussen transacties.
        
        # 1. Bereken cumstratieve stand op de exacte transactiemomenten
        qty_on_tx = tx_p.cumsum()
        
        # 2. Maak ook een dagelijks rooster (nodig voor de lange historie en 'gaten' vullen)
        #    Dit rooster moet aansluiten op start_date (5 jaar geleden)
        now = pd.Timestamp.now()
        full_daily_index = pd.date_range(start=start_date, end=now, freq="D")
        
        # 3. Combineer de exacte transactiemomenten met het dagelijkse rooster
        #    Zo hebben we én punten op 00:00 (voor de lange termijn) én punten op 13:00 (als er gekocht is)
        combined_index = qty_on_tx.index.union(full_daily_index).sort_values()
        
        # 4. Reindex naar dit gecombineerde rooster en vul vooruit (ffill)
        #    De transacties (qty_on_tx) zijn leidend. Het dagrooster neemt de stand over van de laatste tx.
        #    We gebruiken reindex op qty_on_tx, maar moeten opletten dat 'nieuwe' dagen de waarde krijgen.
        #    Beter: concat en dan ffill? Of reindex met method='ffill'?
        
        #    Slimmer: We reindexen qty_on_tx naar de combined_index met ffill.
        #    Echter, qty_on_tx begint pas bij de eerste aankoop. Dagen d'rvoor worden NaN (en later 0).
        daily_qty = qty_on_tx.reindex(combined_index, method='ffill').fillna(0)
        
        # (Oude Code, deleted to avoid confusion)
        # daily_qty = tx_p.resample("D").sum().cumsum()
        # ...
        # normal reindex logic replaced by above.
        
        # Helper functie om series op te halen uit yf resultaat
        def get_price_series(data_obj, t):
            try:
                if isinstance(data_obj.columns, pd.MultiIndex):
                    if t in data_obj.columns.levels[0]:
                        return data_obj[t]["Close"]
                # Fallback if structure is different (e.g. single ticker not creating multiindex level 0 properly sometimes)
                if "Close" in data_obj.columns:
                     return data_obj["Close"]
            except:
                pass
            return pd.Series(dtype=float)

        price_series_daily = get_price_series(yf_data, ticker)
        price_series_hourly = get_price_series(yf_data_hourly, ticker)

        if price_series_daily.empty and price_series_hourly.empty:
            continue
            
        # 1. Verwerk Daily
        # Zorg dat de price_series tijdzone-informatie kwijtraakt
        if price_series_daily.index.tz is not None:
             price_series_daily.index = price_series_daily.index.tz_localize(None)
        price_series_daily.index = price_series_daily.index.normalize() # 00:00

        # 2. Verwerk Hourly
        if not price_series_hourly.empty:
             if price_series_hourly.index.tz is not None:
                # Convert to local/naive to match daily (assuming local time vs UTC doesn't break logic too much, 
                # strictly speaking mixing UTC and Local is bad, but for dashboard display naive is often easiest)
                # Better: tz_convert to 'Europe/Amsterdam' then localize(None)? 
                # For now: just strip TZ.
                price_series_hourly.index = price_series_hourly.index.tz_localize(None)

        # 3. Stitch: Daily tot 8 dagen geleden, daarna Hourly
        # Zodat 'oude' data (langer dan 8 dagen geleden) gewoon daily is, 
        # en alleen de laatste week (+ beetje buffer) in detail is.
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=8)
        
        # Filter daily to be BEFORE the hourly data starts (roughly)
        # Or just take everything before cutoff
        part1 = price_series_daily[price_series_daily.index < cutoff]
        
        # Part 2 is hourly data
        part2 = price_series_hourly
        
        # Combineer
        full_price_series = pd.concat([part1, part2]).sort_index()
        
        # Remove duplicates (if partial overlap)
        full_price_series = full_price_series[~full_price_series.index.duplicated(keep='last')]
             
        # Maak dataframe van de prices
        hist_df = full_price_series.to_frame(name="price")
        
        # (Oude logica voor latest_data weghalen, want hourly data dekt dit nu beter)

        if daily_qty.index.tz is not None:
            daily_qty.index = daily_qty.index.tz_localize(None)
        
        if hist_df.index.tz is not None:
            hist_df.index = hist_df.index.tz_localize(None)

        # CORRECTIE: We gebruiken nu de index van hist_df (die Daily + Hourly combineert).
        # We reindexen de daily_qty naar deze fijnmazige index.
        # aligned_qty behoudt de 00:00 waarden en ffill't ze naar de uren.
        aligned_qty = daily_qty.reindex(hist_df.index, method='ffill').fillna(0)
        
        combined_df = pd.DataFrame(index=hist_df.index)
        combined_df["price"] = hist_df["price"]
        combined_df["quantity"] = aligned_qty
        
        combined_df["product"] = p
        combined_df["ticker"] = ticker
        
        # Bereken waarde
        combined_df["value"] = combined_df["quantity"] * combined_df["price"]
        
        # Filter rijen waar we nog niks hadden
        # Na reindex kunnen er NaNs zijn in price (als daily_qty eerder begint dan available price history)
        combined_df = combined_df.dropna(subset=["price"])
        # We verwijderen rows met quantity 0 NIET meer, omdat we de prijslijn (secondary y) 
        # ook willen zien als we het aandeel nog niet hadden.
        # combined_df = combined_df[combined_df["quantity"] != 0]
        
        if not combined_df.empty:
            history_frames.append(combined_df)
        # else:
            # st.write(f"DEBUG: Combined DF empty for {ticker} after merge/dropna")

    if not history_frames:
        return pd.DataFrame()
        
    final_df = pd.concat(history_frames)
    # Zorg dat de index een naam heeft, zodat reset_index() een kolom 'date' maakt
    final_df.index.name = "date"
    return final_df.reset_index()



# Refactored PriceManager logic replaced by module import



@fragment(run_every=30) # Simplified refresh rate for cleaner code
def render_metrics(df: pd.DataFrame, price_manager, config_manager) -> None:
    """Render metrics with auto-refresh using PriceManager."""
    # Build positions
    positions = build_positions(df)
    
    # Live koersen en actuele waarde per positie
    if not positions.empty:
        # Resolve tickers using PriceManager
        positions["ticker"] = positions.apply(
            lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1
        )
        
        # Fetch prices using PriceManager
        # We can iterate or parallelize, but cache handles it.
        # Check if we need to pre-warm cache? 
        # For now, just apply the get_live_price method.
        positions["last_price"] = positions["ticker"].apply(price_manager.get_live_price)
        positions["prev_close"] = positions["ticker"].apply(price_manager.get_prev_close)
        positions["midnight_price"] = positions["ticker"].apply(price_manager.get_midnight_price)
        
        # Calculate current value
        positions["current_value"] = positions.apply(
            lambda r: (
                r["quantity"] * r["last_price"]
                if pd.notna(r.get("last_price")) and pd.notna(r.get("quantity"))
                else pd.NA
            ),
            axis=1,
        )

        # Daily P/L logic
        def calc_daily(r):
            lp = r.get("last_price")
            qty = r.get("quantity")
            if pd.isna(lp) or pd.isna(qty): return pd.NA
            
            # Base price: prefer midnight for crypto, prev_close for others (or midnight if available?)
            # Refactored standard: use midnight price if available (start of day), else prev_close.
            base = r.get("midnight_price")
            if pd.isna(base) or base == 0:
                base = r.get("prev_close")
            
            if pd.notna(base) and base > 0:
                return qty * (lp - base)
            return pd.NA

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


    # Globale samenvatting
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
    
    # compute total costs for display
    # Totaal Kosten = Netto Inleg = (Aankopen + Fees) - (Verkopen + Dividenden)
    total_costs = abs(total_buys) + total_fees - abs(total_sells) - total_dividends
    
    # compute total P/L as sum of each position's profit/loss (current + net cashflow)
    if not positions.empty:
        positions["pl_eur"] = positions.apply(
            lambda r: r.get("current_value", 0.0) + r.get("net_cashflow", 0.0),
            axis=1,
        )
        # OUDE METHODE (mist gerealiseerde resultaten van gesloten posities):
        # total_result = positions["pl_eur"].sum()
        
        # NIEUWE METHODE: Consistentie met Totale Kosten
        # Totaal Resultaat = Huidige Waarde - (Netto Inleg + Kosten - Dividenden)
        # Oftewel: Huidige Waarde - Totale Kosten
        total_result = total_market_value - total_costs
    else:
        # Ook als er geen open posities zijn, kan er nog wel gerealiseerd resultaat zijn (uit transacties)
        # Bijv. alles verkocht -> waarde=0, kosten=negatief (winst) of positief (verlies)
        total_result = total_market_value - total_costs

    # percentage relative to total amount spent buying (including fees)
    total_spent = abs(total_buys) + total_fees
    if pd.notna(total_spent) and total_spent != 0:
        pct_total = (total_result / total_spent * 100.0)
    else:
        pct_total = 0.0

    # Layout: metrics row (now 4 columns)
    # Periode weergeven
    if "value_date" in df.columns and not df["value_date"].empty:
        min_date = df["value_date"].min()
        max_date = df["value_date"].max()
        period_str = f"{min_date.strftime('%B %Y')} - {max_date.strftime('%B %Y')}"
        st.markdown(f"**Periode data:** {period_str}")
    
    col1, col2, col3 = st.columns(3)
    help_txt = (
        f"Aankopen: {format_eur(abs(total_buys))}  |  "
        f"Fees: {format_eur(total_fees)}  |  "
        f"Verkopen: -{format_eur(abs(total_sells))}  |  "
        f"Dividend: -{format_eur(total_dividends)}"
    )
    col1.metric("Totale Kosten (Netto Inleg)", format_eur(total_costs), help=help_txt)
    col2.metric("Huidige marktwaarde (live)", format_eur(total_market_value))
    col3.metric("Total P/L", format_eur(total_result), delta=format_pct(pct_total), delta_color="normal",
               help="Berekening: Marktwaarde - Totale kosten (inclusief gerealiseerd resultaat)")

    # second row of other metrics (dividend only now)
    col5, col6 = st.columns(2)
    col5.metric("Ontvangen dividend", format_eur(total_dividends))
    col6.write("")  # placeholder column


@fragment(run_every=30)
def render_overview(df: pd.DataFrame, config_manager, price_manager) -> None:
    """Render de open posities tabel en allocatie chart met auto-refresh."""
    positions = build_positions(df)
    
    if not positions.empty:
        # Resolve tickers
        positions["ticker"] = positions.apply(
            lambda r: price_manager.resolve_ticker(r.get("product"), r.get("isin")), axis=1
        )
        
        # Fetch live prices via PriceManager
        positions["last_price"] = positions["ticker"].apply(price_manager.get_live_price)

        positions["current_value"] = positions.apply(
            lambda r: (
                r["quantity"] * r["last_price"]
                if pd.notna(r.get("last_price")) and pd.notna(r.get("quantity"))
                else pd.NA
            ),
            axis=1,
        )
        
        # Categorisatie en Naamverkorting
        positions["Category"] = positions["isin"].apply(lambda x: "Crypto" if str(x).startswith("XFC") else "ETFs & Stocks")
        positions["Display Name"] = positions["product"].apply(_shorten_name)
        
        st.subheader("Open posities (afgeleid uit transacties)")
        
        for cat in ["ETFs & Stocks", "Crypto"]:
            cat_df = positions[positions["Category"] == cat].copy()
            if not cat_df.empty:
                st.markdown(f"#### {cat}")
                display = cat_df.copy()
                
                # include previous close if available (for reference)
                display["prev_close"] = display["ticker"].apply(price_manager.get_prev_close)
                
                # --- CALCULATION LOGIC: MATCH DEGIRO (Include Fees, Sells, Divs) ---
                # Net Invested = (Buys + Fees) - (Sells + Dividends)
                # This represents the actual "Netto Inleg" remaining in the position.
                buy_val = display["invested"]
                sell_val = display["total_sells"].fillna(0.0)
                fee_val = display["total_fees"].abs().fillna(0.0)
                div_val = display["total_dividends"].fillna(0.0)
                
                display["Totaal geinvesteerd"] = (buy_val + fee_val - sell_val - div_val)
                
                # Create a "Help/Info" column with breakdown
                def _make_info(row):
                    b = format_eur(row["invested"])
                    f = format_eur(abs(row["total_fees"]))
                    s = format_eur(row["total_sells"])
                    d = format_eur(row["total_dividends"])
                    # Use a compact format
                    return f"Buy: {b} | Fee: {f} | Sell: {s} | Div: {d}"

                display["ℹ️"] = display.apply(_make_info, axis=1)

                # Winst/verlies berekening (EUR)
                # Net profit = Current Value + Net Cashflow (which sums buys(-), sells(+), fees(-), divs(+))
                display["Winst/verlies (EUR)"] = (display["current_value"] + display["net_cashflow"])
                
                # Format for display
                display["Totaal geinvesteerd"] = display["Totaal geinvesteerd"].map(format_eur)
                display["Huidige waarde"] = display["current_value"].map(format_eur)
                display["Winst/verlies (EUR)"] = display["Winst/verlies (EUR)"].map(format_eur)

                def _pl_pct(row: pd.Series) -> float | None:
                    cur = row.get("current_value")
                    net_cf = row.get("net_cashflow")
                    # Use the Net Invested as basis calculation?
                    # If I sold half, my invested went down. My P/L is relative to remaining invested?
                    # Or relative to "Netto Inleg"?
                    # DeGiro typically uses: Result / Netto Inleg.
                    # Net Invested calculated above IS Netto Inleg.
                    
                    # Re-calculate net invested float for division (since column is now string formatted)
                    # better to use the raw series before formatting, but here we are row-wise.
                    # Let's trust the previous step or just recompute.
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

                # Columns to show
                cols = [
                    "Display Name", "quantity", "Huidige waarde", 
                    "Totaal geinvesteerd", "Winst/verlies (EUR)", "Winst/verlies (%)",
                    "ℹ️" # Breakdown column
                ]
                
                # Configure columns
                st.dataframe(
                    display[cols],
                    use_container_width=True,
                    column_config={
                        "Display Name": st.column_config.TextColumn("Product", width="medium"),
                        "quantity": st.column_config.NumberColumn("Aantal", format="%.4f"),
                        "Huidige waarde": st.column_config.TextColumn("Waarde", help="Huidige marktwaarde (Aantal * Laatste Prijs)"),
                        "Totaal geinvesteerd": st.column_config.TextColumn(
                            "Netto Inleg", 
                            help="Totale netto investering: (Aankopen + Fees) - (Verkopen + Dividend). Zie 'ℹ️' voor details."
                        ),
                        "Winst/verlies (EUR)": st.column_config.TextColumn("W/V (€)"),
                        "Winst/verlies (%)": st.column_config.TextColumn("W/V (%)"),
                        "ℹ️": st.column_config.TextColumn(
                            "Info", 
                            help="Breakdown: Buy | Fee | Sell | Div",
                            width="large"
                        ),
                    },
                    hide_index=True
                )
                
                # End of category rendering

        # Portefeuilleverdeling & Rebalancing
        st.subheader("Portefeuilleverdeling & Rebalancing")
        
        # --- CONFIG PERSISTENCE ---
        # Managed by ConfigManager
        # saved_targets = config_manager.get_targets() # Legacy
        saved_assets = config_manager.get_assets() # NEW Rich Objects
        
        # --- UI FOR ADDING NEW ASSETS ---
        with st.expander("➕ Nieuw aandeel toevoegen aan verdeling"):
            col_add_1, col_add_2 = st.columns(2)
            # SWAPPED INPUTS per user request
            with col_add_1:
                new_asset_name = st.text_input("Productnaam (voor weergave)", key="new_asset_name", help="Leesbare naam, bijv. 'Vanguard World'")
            with col_add_2:
                new_asset_key = st.text_input("Ticker / ISIN (Key)", key="new_asset_key", help="Unieke identifier, bijv. 'VWCE.DE' of 'IE00...'")
            
            new_asset_target = st.number_input("Gewenst percentage (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, key="new_asset_target")
            
            # Load persisted settings (stock fee in EUR, crypto fee in %)
            rb_settings = config_manager.get_settings()
            col_fee_1, col_fee_2 = st.columns(2)
            with col_fee_1:
                stock_fee_eur = st.number_input("Standaard fee aandelen (€)", min_value=0.0, step=0.1, value=float(rb_settings.get("stock_fee_eur", 1.0)), help="Standaard transactiekosten per order voor aandelen (EUR)")
            with col_fee_2:
                crypto_fee_pct = st.number_input("Standaard crypto fee (%)", min_value=0.0, step=0.01, value=float(rb_settings.get("crypto_fee_pct", 0.29)), help="Procentuele fee voor crypto (bijv. 0.29 betekent 0.29%)")
            # Persist settings when changed
            if stock_fee_eur != rb_settings.get("stock_fee_eur") or crypto_fee_pct != rb_settings.get("crypto_fee_pct"):
                config_manager.update_settings(stock_fee=stock_fee_eur, crypto_fee=crypto_fee_pct)

            if st.button("Voeg toe"):
                # Clean inputs
                clean_key = new_asset_key.strip() if new_asset_key else ""
                clean_name = new_asset_name.strip() if new_asset_name else ""
                
                if clean_key:
                    # Save Asset (Key -> {target, name}) in one go
                    config_manager.set_asset(clean_key, target_pct=new_asset_target, display_name=clean_name)
                    
                    # Force save/reload - actually variable just needs refresh
                    saved_assets = config_manager.get_assets()

                    # Resolve/Warmup
                    try:
                        resolved = price_manager.resolve_ticker(clean_key)
                        if resolved:
                            price_manager.get_live_price(resolved) # trigger cache
                    except:
                        pass

                    st.toast(f"{clean_key} ({clean_name or 'Geen naam'}) toegevoegd!", icon="✅")
                    st.rerun()
                else:
                    st.error("Voer een Ticker/ISIN in.")


        alloc = positions.copy()
        alloc["alloc_value"] = alloc["current_value"].fillna(alloc["invested"])
        alloc = alloc[alloc["alloc_value"].notna() & (alloc["alloc_value"] > 0)]
        
        # Calculate Total Invested Value
        total_value = alloc["alloc_value"].sum() if not alloc.empty else 0.0
        
        # Determine if we should show table even if empty (targets exist?)
        show_table = (total_value > 0) or bool(saved_assets)

        if show_table:
            total_value = max(total_value, 1.0) # avoid div0

            if not alloc.empty:
                alloc["current_pct"] = (alloc["alloc_value"] / total_value) * 100.0
                alloc["Display Name"] = alloc["product"].apply(_shorten_name)
            else:
                alloc = pd.DataFrame(columns=["Display Name", "current_pct", "alloc_value"])
            
            # Prepare dataframe for editor
            editor_df = alloc[["Display Name", "current_pct"]].copy()
            # RENAME COLUMN per user request: "Ticker/ISIN" -> "Productnaam" for display
            # We must map existing display names (which might be tickers) to valid ProductNames
            editor_df = editor_df.rename(columns={"Display Name": "Productnaam", "current_pct": "Huidig %"})
            editor_df["Huidig %"] = editor_df["Huidig %"].round(1)
            
            # MERGE WATCHLIST
            # 'saved_assets' keys are Ticker/ISIN. We need to find their display name.
            # If no display name, use key.
            # But wait, editor_df currently has "product" (key) as "Display Name"? 
            # No, 'product' in filtered alloc is usually Ticker/ISIN or ShortName. 
            # We need to ensure we align by KEY (Ticker/ISIN) but show NAME.
            
            # Let's rebuild editor_df carefully to separate Key and Display
            # 1. Get Keys of current positions
            current_keys = set(alloc["product"].unique()) if "product" in alloc.columns else set()
            
            # 2. Build complete list of keys (Current + Saved)
            all_keys = current_keys.union(saved_assets.keys())
            
            rows = []
            for key in all_keys:
                # Get Name
                name = config_manager.get_product_name(key) # Returns name or key
                
                # Get Current % (if in alloc)
                curr_pct = 0.0
                match = alloc[alloc["product"] == key]
                if not match.empty:
                    curr_pct = match.iloc[0]["current_pct"]
                
                # Get Target
                target = 0.0
                if key in saved_assets:
                    target = float(saved_assets[key].get("target_pct", 0.0))
                
                rows.append({
                    "Productnaam": name,
                    "Ticker/ISIN": key, # Keep for logic, hide later?
                    "Huidig %": round(curr_pct, 1),
                    "Doel %": target
                })
            
            editor_df = pd.DataFrame(rows)
            # Ensure columns order and Set Index to Ticker/ISIN (to hide it visually but keep it)
            if not editor_df.empty:
                editor_df.set_index("Ticker/ISIN", inplace=True)
                editor_df = editor_df[["Productnaam", "Huidig %", "Doel %"]]
            else:
                editor_df = pd.DataFrame(columns=["Productnaam", "Huidig %", "Doel %"])

            # Gebruik st.form
            with st.form("rebalance_form"):
                st.write("Pas hieronder de gewenste verdeling aan:")
                edited_df = st.data_editor(
                    editor_df,
                    column_config={
                        "Huidig %": st.column_config.NumberColumn(format="%.1f %%", disabled=True),
                        "Doel %": st.column_config.NumberColumn(format="%.1f %%", min_value=0, max_value=100, step=0.1, required=True),
                        "Productnaam": st.column_config.TextColumn(disabled=True),
                    },
                    use_container_width=True,
                    hide_index=True, # Hides the Ticker/ISIN index!
                    key="rebalance_editor"
                )
                
                st.markdown("---")
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
                    st.write("") # Padding
                    prevent_sell = st.checkbox("Voorkom verkoop", value=False, help="Schakel dit in om alleen bijkopen te suggereren.")
                
                submitted = st.form_submit_button("📊 Update Berekening & Grafiek", type="primary")

            if submitted:
                # Save changes when submitted
                # Index is Ticker/ISIN (preserved even if hidden)
                new_targets = dict(zip(edited_df.index, edited_df["Doel %"]))
                
                current_t = config_manager.get_targets()
                # Remove deleted ones? No, this is just updating percentages of existing editor items.
                for p, t in new_targets.items():
                    config_manager.set_target(p, t)
                st.toast("Verdeling opgeslagen!", icon="💾")

            # --- REMOVE OPTION ---
            # Extract watchlist items (those with 0% current) for removal
            # Filter based on index (Ticker/ISIN) and column (Huidig %)
            if not editor_df.empty and "Huidig %" in editor_df.columns:
                 watchlist_items = editor_df[editor_df["Huidig %"] == 0.0].index.tolist()
            else:
                 watchlist_items = []

            if watchlist_items:
                # Map key->name using display column (Productnaam)
                key_to_name = editor_df["Productnaam"].to_dict() # index is key
                # options: "Name (Ticker)"
                options = [f"{key_to_name[k]} ({k})" for k in watchlist_items]
                
                to_remove_display = st.multiselect("Verwijder nieuwe aandelen:", options)
                if st.button("Verwijder geselecteerde"):
                    for item in to_remove_display:
                        # extract key (last part in parens?) 
                        k = item.split("(")[-1].strip(")")
                        config_manager.remove_target(k)
                    st.toast("Aandelen verwijderd!", icon="🗑️")
                    st.rerun()


            # --- 2. Calculate Actions (Phase 1: Determine Actions and Totals) ---
            total_target = edited_df["Doel %"].sum()
            # Allow small float error (99.9 - 100.1 is fine)
            if abs(total_target - 100.0) > 0.2:
                st.warning(f"Totaal doelpercentage is {total_target:.1f}% (moet ~100% zijn).")

            new_total_value = total_value + extra_budget
            
            # PRE-CALCULATE SCALING FOR BUY-ONLY MODE
            buy_gaps = []
            for idx, row in edited_df.iterrows():
                # Use Ticker/ISIN (Index) to match back to alloc
                key = idx 
                
                # Find current value in alloc
                # alloc has 'product' column as key
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

            # Ensure price manager watches any new products 
            # (Implicitly handled by get_live_price, but we can do a pass to resolve/warmup)
            # Replaced by simple pass as PriceManager is robust.

            raw_actions = []
            # Load rebalance settings
            rb_settings = config_manager.get_settings()

            for idx, row in edited_df.iterrows():
                product_key = idx # Ticker/ISIN is the Index now
                target_pct = row["Doel %"]
                # current_pct_rounded = row["Huidig %"] 
                
                # Fetch Display Name from Config (if available) - already in row["Productnaam"]
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
                    # Resolve ticker and fetch price via PriceManager
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
                
                # Use key for crypto detection if name fails
                check_str = str(product_key).upper() + " " + str(display_name).upper()
                is_crypto = any(x in check_str for x in ["BTC", "ETH", "COIN", "CRYPTO", "BITCOIN", "ETHEREUM"])
                
                if is_crypto:
                    qty_to_trade = qty_calculated
                    executed_diff = diff
                else:
                    qty_to_trade = round(qty_calculated)
                    executed_diff = qty_to_trade * last_price
                
                # Preliminary Fee (use persisted settings)
                fee = 0.0
                if abs(qty_to_trade) > 0:
                    if is_crypto:
                        fee_pct = float(rb_settings.get("crypto_fee_pct", 0.29))
                        fee = abs(executed_diff) * (fee_pct / 100.0)
                    else:
                        fee = float(rb_settings.get("stock_fee_eur", 1.0))

                # Validate Action
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
                    "Productnaam": display_name, # NEW COLUMN
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

            # --- PHASE 1.5: Budget Adjustment (Lumpy Correction) ---
            # If net deposit > budget + tolerance (10%), reduce buys
            def calc_net(actions):
                buys = sum(a["Verschil (EUR)"] + a["Kosten (Fee)"] for a in actions if a["Actie"] == "Kopen")
                sells = sum(abs(a["Verschil (EUR)"]) - a["Kosten (Fee)"] for a in actions if a["Actie"] == "Verkopen")
                return buys - max(0, sells)

            tolerance = extra_budget * 0.1
            current_net = calc_net(raw_actions)
            if current_net > extra_budget + tolerance:
                # Sort buys by price (descending) to tackle lumpy ETFs first
                buys_indices = [i for i, a in enumerate(raw_actions) if a["Actie"] == "Kopen" and not a["is_crypto"]]
                buys_indices.sort(key=lambda i: raw_actions[i]["last_price"], reverse=True)
                
                for idx in buys_indices:
                    action_item = raw_actions[idx]
                    # Reduce by 1 share
                    if action_item["Aantal"] >= 1:
                        action_item["Aantal"] -= 1
                        action_item["Verschil (EUR)"] = action_item["Aantal"] * action_item["last_price"]
                        # Adjust fee if zero
                        if action_item["Aantal"] == 0:
                            action_item["Kosten (Fee)"] = 0.0
                            action_item["Actie"] = "-"
                        else:
                            # Re-calc fee (usually remains same for ETFs, but good practice)
                            # Use Productnaam or Ticker/ISIN for check
                            check_str = str(action_item["Productnaam"]) + str(action_item["Ticker/ISIN"])
                            is_core = "Vanguard" in check_str or action_item["isin"] == "IE00BK5BQT80"
                            action_item["Kosten (Fee)"] = 1.0 if is_core else 3.0
                        
                        current_net = calc_net(raw_actions)
                        if current_net <= extra_budget + tolerance:
                            break

            # --- Phase 2: Calculate Projected Results ---
            total_executed_buys = sum(a["Verschil (EUR)"] for a in raw_actions if a["Actie"] == "Kopen")
            total_executed_sells = sum(abs(a["Verschil (EUR)"]) for a in raw_actions if a["Actie"] == "Verkopen")
            actual_new_total = total_value + total_executed_buys - total_executed_sells
            
            results = []
            for act in raw_actions:
                new_val_projected = act["curr_val"] + act["Verschil (EUR)"]
                new_pct_projected = (new_val_projected / actual_new_total) * 100.0 if actual_new_total > 0 else 0.0
                
                results.append({
                    "Ticker/ISIN": act["Ticker/ISIN"],
                    "Productnaam": act["Productnaam"], # DISPLAY NAME
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
            
            # Show Action Table
            st.markdown("#### Actie Advies")
            st.markdown("Dit overzicht houdt rekening met het feit dat aandelen in hele stuks gekocht worden en bevat de transactiekosten.")
            
            # Use Productnaam logic as requested: 
            # REMOVE Ticker/ISIN from VIEW
            
            st.dataframe(
                res_df[["Productnaam", "Actie", "Verschil (EUR)", "Aantal", "Kosten (Fee)", "Nieuw %"]].style.format({
                    "Verschil (EUR)": "€ {:.2f}",
                    "Aantal": "{:.4f}",
                    "Kosten (Fee)": "€ {:.2f}",
                    "Nieuw %": "{:.2f} %"
                }),
                use_container_width=True,
                hide_index=True
            )

            # --- FINANCIAL SUMMARY ---
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
            
            # --- 3. Visualize Current vs Target (Concentric Donut) ---
            st.markdown("#### Huidig vs Doel (Overlay)")
            
            import plotly.graph_objects as go
            
            fig = go.Figure()

            # Outer Ring = Doel Verdeling (Target)
            fig.add_trace(go.Pie(
                labels=res_df["Productnaam"],
                values=res_df["Doel Waarde"],
                name="Doel",
                hole=0.6, # Grote ring
                sort=False,
                direction='clockwise',
                showlegend=True,
                marker=dict(line=dict(color='#000000', width=2))
            ))

            # Inner Circle = Huidige Verdeling (Current)
            fig.add_trace(go.Pie(
                labels=res_df["Productnaam"],
                values=res_df["Huidige Waarde"], 
                name="Huidig",
                hole=0, 
                domain={'x': [0.25, 0.75], 'y': [0.25, 0.75]}, # Kleiner, inside
                sort=False,
                direction='clockwise',
                showlegend=False, # Shared legend
                textinfo='label+percent',
                textposition='inside'
            ))

            fig.update_layout(
                title="Buitenring = Doel  |  Binnen = Huidig",
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=30, b=0, l=0, r=0)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
    else:
        st.caption("Geen open posities gevonden op basis van de transacties.")



# Function for static tables/charts that doesn't need constant refresh/reset
def render_charts(df: pd.DataFrame, history_df: pd.DataFrame, trading_volume: pd.DataFrame, drive=None, config_manager=None, price_manager=None) -> None:
    st.markdown("---")
    tab_overview, tab_balance, tab_history, tab_transactions = st.tabs(
        ["📈 Overzicht", "💰 Saldo & Cashflow", " Historie", "📋 Transacties"]
    )

    with tab_overview:
        # Dit fragment ververst elke 30 seconden
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
            fig_cf.update_layout(dragmode=False)
            st.plotly_chart(fig_cf, use_container_width=True, config={'scrollZoom': False})
        else:
            st.caption("Geen aan- of verkopen gevonden.")
    
    with tab_history:
        st.subheader("Historische waardeontwikkeling")
        
        # 1. Globale Tijdselectie voor dit tabblad
        period_options = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD", "5Y", "ALL"]
        # Default op 1M (index 2)
        selected_period = st.radio("Kies periode:", period_options, index=2, horizontal=True, label_visibility="collapsed")
        
        # Bepaal startdatum en resample-logica
        now = pd.Timestamp.now()
        start_date = None
        resample_rule = None # None = keep detailed (hourly)
        
        if selected_period == "1D":
            start_date = now - pd.Timedelta(days=1)
            resample_rule = '5min' # Forceer 5m rooster (zodat ffill/dropna logica werkt)
        elif selected_period == "1W":
            start_date = now - pd.Timedelta(weeks=1)
            resample_rule = '1H' # 1 Week view: Uurlijkse updates (niet 5m) start_date = now - pd.Timedelta(weeks=1)
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
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                fig_hist = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Filter & Resample logica (Obv globale selectie)
                df_chart = subset.copy()
                if "date" in df_chart.columns:
                    df_chart = df_chart.set_index("date").sort_index()

                # --- TIMEZONE CONVERSION (Amsterdam) ---
                try:
                    if df_chart.index.tz is None:
                        df_chart.index = df_chart.index.tz_localize("UTC")
                    df_chart.index = df_chart.index.tz_convert("Europe/Amsterdam")
                except:
                    pass
                
                if start_date:
                    # Ensure start_date is comparable (localize if needed)
                    s_date = pd.Timestamp(start_date)
                    if s_date.tz is None and df_chart.index.tz is not None:
                        s_date = s_date.tz_localize(df_chart.index.tz)
                    df_chart = df_chart[df_chart.index >= s_date]

                # --- GAP REMOVAL SETUP ---
                # Check for Crypto BEFORE resampling
                # Check for Crypto BEFORE resampling
                is_crypto = any(x in str(selected_product).upper() for x in ["BTC", "ETH", "COIN", "CRYPTO", "BITCOIN", "ETHEREUM"])
                ticker = price_manager.resolve_ticker(selected_product, None)
                if ticker and ("BTC" in ticker or "ETH" in ticker):
                    is_crypto = True

                if resample_rule:
                    if selected_period in ["1D", "1W"] and not is_crypto:
                         # Stocks Short-Term: We want to HIDE gaps (nights/weekends).
                         # So we drop the empty bins that resample created.
                         df_chart = df_chart.resample(resample_rule).last().dropna()
                    else:
                        # Crypto or Long-Term: We want CONTINUOUS lines (no visual breaks).
                        # So we fill the gaps with the last known value.
                        df_chart = df_chart.resample(resample_rule).last().ffill()

                # Reset index voor Plotly (zodat 'date' weer een kolom is)
                # Als we niet geresampled hebben, willen we OOK resetten als date in de index staat.
                df_chart = df_chart.reset_index()

                xaxis_type = "date"
                x_values = df_chart["date"]
                
                if selected_period in ["1D", "1W"] and not is_crypto:
                    xaxis_type = "category"
                    # Format datum naar string string voor category axis
                    # Anders plot hij lelijke timestamps
                    x_values = df_chart["date"].dt.strftime("%d-%m %H:%M")
                    # Let op: dit maakt x-as labels strings.
                
                # --- PLOTLY UPDATE ---
                
                # Gebruik nu df_chart ipv subset
                fig_hist.add_trace(go.Scatter(x=x_values, y=df_chart["value"], name="Waarde in bezit (EUR)", mode='lines', connectgaps=True, line=dict(color="#636EFA")), secondary_y=False)
                fig_hist.add_trace(go.Scatter(x=x_values, y=df_chart["price"], name="Koers (EUR)", mode='lines', connectgaps=True, line=dict(color="#EF553B", dash='dot')), secondary_y=True)
                
                # Force autoscale (blijft nodig)
                fig_hist.update_yaxes(title_text="Totale Waarde (€)", secondary_y=False, showgrid=True, autorange=True, fixedrange=False, rangemode="normal")
                fig_hist.update_yaxes(title_text="Koers per aandeel (€)", secondary_y=True, showgrid=False, autorange=True, fixedrange=False, rangemode="normal")
                
                fig_hist.update_layout(
                    title_text=f"Historie voor {selected_product}", hovermode="x unified",
                    legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255, 255, 255, 0)"),
                    # XAXIS: Type dynamisch zetten
                    xaxis=dict(
                        type=xaxis_type,
                        rangeslider=dict(visible=False),
                        nticks=10 if xaxis_type == "category" else None # Voorkom clutter bij category
                    ),
                    dragmode=False,
                    yaxis=dict(autorange=True, fixedrange=False, rangemode="normal")
                )
                # Bereken 15% padding voor de assen voor een mooiere look -- REMOVED for autoscaling
                # val_min, val_max = subset["value"].min(), subset["value"].max()
                # val_range = max(val_max - val_min, 1.0)
                # val_lims = [val_min - 0.15 * val_range, val_max + 0.15 * val_range]
                
                # price_min, price_max = subset["price"].min(), subset["price"].max()
                # price_range = max(price_max - price_min, 1.0)
                # price_lims = [price_min - 0.15 * price_range, price_max + 0.15 * price_range]

                # FORCE AUTOSCALE:
                # rangemode="normal" ensures it doesn't force 0 to be included.
                # autorange=True enables dynamic scaling.
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
                    
                    # --- Apply GLOBAL Filter/Resample Logic ---
                    # We processen de compare_df als geheel, en resamplen per product (groupby?)
                    # Eenvoudiger: Eerst filteren op datum
                    if "date" in compare_df.columns:
                        compare_df = compare_df.set_index("date").sort_index()

                    # --- TIMEZONE CONVERSION (Amsterdam) ---
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
                    
                    # Resampling moet per groep (product) gebeuren anders vermengen we data
                    if resample_rule:
                         # Group by product and resample each group
                         # Check if we have columns left to resample?
                         # resample(...).last() takes the last value of the period.
                         # Use ffill() to fill weekends/gaps
                         compare_df = compare_df.groupby("product").resample(resample_rule).last().ffill()
                         
                         # FIX: Drop columns that collide with index names before reset
                         # This prevents "ValueError: cannot insert ..., already exists"
                         for name in compare_df.index.names:
                             if name in compare_df.columns:
                                 compare_df = compare_df.drop(columns=[name])
                                 
                         # The grouping puts product in index. resample puts date in index.
                         # df has (product, date) index.
                         compare_df = compare_df.reset_index()
                    else:
                        compare_df = compare_df.reset_index()

                    # Pas naamverkorting toe voor de legenda
                    if "product" in compare_df.columns:
                        compare_df["product"] = compare_df["product"].apply(_shorten_name)
                    
                    fig_compare = px.line(
                        compare_df, x="date", y="value", color="product", 
                        title="Waarde per aandeel in de tijd (EUR)", 
                        labels={"value": "Waarde (EUR)", "date": "Datum", "product": "Product"}
                    )
                    
                    # Ensure gaps are connected visually as well
                    fig_compare.update_traces(connectgaps=True)
                
                fig_compare.update_layout(
                    legend=dict(orientation="h", yanchor="top", y=-0.4, xanchor="left", x=0),
                    yaxis=dict(autorange=True, fixedrange=False, rangemode="normal"),
                    xaxis=dict(
                        type="date",
                        rangeslider=dict(visible=False)
                    ),
                    dragmode=False
                )
                st.plotly_chart(fig_compare, use_container_width=True, config={'scrollZoom': False})
            else:
                st.info("Geen data om te tonen.")
        else:
            st.info("Geen historische data beschikbaar.")
            
    with tab_transactions:
        st.subheader("Ruwe transactiedata")
        st.dataframe(df, use_container_width=True, height=500)


def main() -> None:
    st.set_page_config(
        page_title="DeGiro Portfolio Dashboard",
        layout="wide",
    )

    st.title("DeGiro Portfolio Dashboard")
    
    sidebar = st.sidebar
    sidebar.header("Instellingen")

    # Uploader key voor reset
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    # 1. Google Drive Connection & Data Laden
    # DRIVE_FOLDER_ID provided by user
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

    # --- INITIALIZE MANAGERS ---
    config_manager = ConfigManager(drive=drive)
    # Ensure settings are loaded or defaults set
    
    price_manager = PriceManager(config_manager=config_manager)

    # 2. File Upload (Nu optioneel als er al sheet data is)
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

    # 3. Samenvoegen van Opgeslagen + Nieuw
    df_raw = pd.DataFrame()
    
    # Eerst Drive data verwerken
    if not df_drive.empty:
        # Fix datumtypes
        for col in ["date", "value_date"]:
            if col in df_drive.columns:
                df_drive[col] = pd.to_datetime(df_drive[col], errors="coerce")
        df_raw = pd.concat([df_raw, df_drive], ignore_index=True)
        
    if not df_new.empty:
        # df_new komt al schoon uit load_degiro_csv
        df_raw = pd.concat([df_raw, df_new], ignore_index=True)

    if df_raw.empty:
        st.warning("Geen data gevonden. Upload een bestand of koppel aan Google Drive.")
        return
    
    # Knoppen voor data-beheer
    if use_drive:
        st.sidebar.markdown("---")
        with st.sidebar.expander("🗑️ Data Beheer"):
            if st.button("🔴 Wis ALLE data", help="Verwijdert alle data uit Drive en leegt de uploader."):
                try:
                    # We overschrijven met een lege dataframe die wel de kolommen heeft
                    empty_df = pd.DataFrame(columns=df_raw.columns)
                    drive.save_data(empty_df)
                    st.cache_data.clear()
                    # Reset ook de file uploader
                    st.session_state["uploader_key"] += 1
                    st.toast("Alle data is gewist!", icon="🗑️")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Kon data niet wissen: {e}")
    
    # Duplicaten verwijderen met een Hybride Sleutel (EXTREEM STRIKT)
    def _make_dedup_key(df_in: pd.DataFrame) -> pd.Series:
        # 1. Datum & Tijd (altijd nodig)
        d = pd.to_datetime(df_in["date"], errors='coerce').dt.strftime("%Y%m%d").fillna("00000000")
        t = df_in["time"].astype(str).str.strip().fillna("00:00")
        
        # 2. Product/ISIN stabilisatie
        # Gebruik ISIN als die er is, anders product
        p_val = df_in["isin"].fillna(df_in["product"]).astype(str).str.strip().str.lower().replace("nan", "")
        
        # 3. Slimme Omschrijving (Substring regel van Jason)
        def _clean_desc(s):
            s = str(s).strip().lower()
            if any(x in s for x in ["vanguard", "future", "hanetf"]):
                return s[:15]
            return s
        
        desc = df_in["description"].apply(_clean_desc)
        
        # 4. Bedrag & Order ID
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

    # 4. Opslaan naar Google Drive (alleen als er nieuwe upload was EN we verbonden zijn)
    if use_drive and not df_new.empty:
        try:
            drive.save_data(df_raw)
            st.toast("Nieuwe data succesvol opgeslagen in Google Drive (CSV)!", icon="💾")
        except Exception as e:
            st.error(f"Fout bij opslaan naar Drive: {e}")
    
    # Filter specifieke producten eruit op verzoek (bijv. test-aandelen)
    if "product" in df_raw.columns:
        df_raw = df_raw[~df_raw["product"].astype(str).str.contains("Aegon", case=False, na=False)]

    # --- ROBUST DATA CLEANING (Post-Merge) ---
    # Ensure amount/balance/fx are clean Floats, handling both:
    # 1. Clean data ("1234.56" or 1234.56)
    # 2. Dirty/Legacy EU strings ("1.234,56") preserved in Drive
    def smart_numeric_clean(series):
        # 0. If already numeric, we are good (but ensure fillna)
        if pd.api.types.is_numeric_dtype(series):
             return series.fillna(0.0)
             
        # 1. Try standard conversion
        # This handles strings "123.45" correctly
        nums = pd.to_numeric(series, errors='coerce')
        
        # 2. Identify items that failed to parse (and weren't null originally)
        # These are likely "1.234,56" strings
        mask_fail = nums.isna() & series.notna()
        
        if mask_fail.any():
            # Apply EU cleaning ONLY to the failed items
            def clean_eu(x):
                s = str(x).replace("EUR", "").replace("USD", "").strip()
                s = s.replace(".", "").replace(",", ".") # 1.234,56 -> 1234.56
                return s
            
            cleaned = series[mask_fail].apply(clean_eu)
            nums.update(pd.to_numeric(cleaned, errors='coerce'))
            
        return nums.fillna(0.0)

    for col in ["amount", "balance", "fx"]:
        if col in df_raw.columns:
            df_raw[col] = smart_numeric_clean(df_raw[col])

    df = enrich_transactions(df_raw)
    
    # Needs price_manager for ticker resolution
    history_df = build_portfolio_history(df, price_manager=price_manager)
    
    trading_volume = build_trading_volume_by_month(df)
    
    render_metrics(df, price_manager=price_manager, config_manager=config_manager)
    render_charts(df, history_df, trading_volume, drive=drive, config_manager=config_manager, price_manager=price_manager)
    


if __name__ == "__main__":
    main()


