import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
from drive_utils import DriveStorage

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

    # Parse dates flexibly (European %d-%m-%Y OR ISO %Y-%m-%d)
    # This prevents date loss when loading back from CSV
    for col in ["date", "value_date"]:
        if col in df.columns:
            # First try dayfirst for DeGiro native exports
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            # If everything becomes NaT, it might be ISO from our own CSV save
            if df[col].isna().all() and not df[col].empty:
                df[col] = pd.to_datetime(df[col], errors="coerce")

    # Helper to parse numeric fields with comma decimal separator
    def _to_float(series: pd.Series) -> pd.Series:
        return (
            series.astype(str)
            .str.replace(".", "", regex=False)  # remove thousands separator if present
            .str.replace(",", ".", regex=False)
            .str.replace('"', "", regex=False)
            .str.strip()
            .replace({"": None})
            .pipe(pd.to_numeric, errors="coerce")
        )

    if "amount" in df.columns:
        df["amount"] = _to_float(df["amount"])
    if "balance" in df.columns:
        df["balance"] = _to_float(df["balance"])

    # Sort chronologisch op valutadatum + tijd
    sort_cols = [c for c in ["value_date", "date", "time"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    return df


def classify_row(description: str) -> str:
    """Zet de omschrijving om in een transaction type."""
    desc = (description or "").strip()

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
            invested=("buy_cash", lambda s: -s.sum()),  # Bruto aankoopwaarde
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
def build_portfolio_history(df: pd.DataFrame) -> pd.DataFrame:
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
        isin = isin_series.iloc[0] if not isin_series.empty else None
        
        ticker = map_to_ticker(p, isin)
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
        yf_data = yf.download(unique_tickers, start=start_date_str, interval="1d", group_by="ticker", progress=False)
        
        # Download HOURLY data voor de laatste 5 dagen (voor gedetailleerde 1d/1w view)
        yf_data_hourly = yf.download(unique_tickers, period="5d", interval="60m", group_by="ticker", progress=False)
        
    except Exception as e:
        st.error(f"Fout bij ophalen historische data: {e}")
        return pd.DataFrame()

    # Verwerk per product
    for p in valid_products:
        ticker = product_map[p]
        
        tx_p = relevant_tx[relevant_tx["product"] == p].copy()
        if tx_p.empty:
            continue
            
        # Zet datum index
        tx_p = tx_p.set_index("value_date")["quantity"].sort_index()
        
        # Resample naar dag om gaten te vullen, daarna cumsum
        daily_qty = tx_p.resample("D").sum().cumsum()
        
        # DEBUG: Check timezone of daily_qty
        # if daily_qty.index.tz is not None:
        #    st.write(f"Daily Qty for {p} has TZ: {daily_qty.index.tz}. Stripping...")
        #    daily_qty.index = daily_qty.index.tz_localize(None)
        
        # Zorg dat de quantity-data doorloopt tot VANDAAG.
        # Anders stopt de grafiek bij de laatste transactie.
        # En zorg OOK dat de grafiek begint bij start_date (5 jaar terug), 
        # ook als de eerste transactie pas later was.
        now = pd.Timestamp.now().normalize()
        
        # Bepaal het volledige bereik d.m.v. start_date en now
        full_index = pd.date_range(start=start_date, end=now, freq="D")
        
        # Reindex en vul gaten. 
        # LOGIC FIX: Eerst reindexen (geeft NaNs), dan ffill() zodat de LAATSTE stand 
        # doorgetrokken wordt naar 'vandaag' (als er geen recente data is).
        # Daarna fillna(0) zodat de periode VÓÓR de eerste aankoop 0 wordt.
        # (Oude situatie met fill_value=0 zorgde dat de toekomst ook 0 werd).
        daily_qty = daily_qty.reindex(full_index).ffill().fillna(0)
        
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

        # 3. Stitch: Daily tot 5 dagen geleden, daarna Hourly
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=5)
        
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


# Eenvoudige mapping van ISIN/product naar een yfinance-ticker.
# Dit kun je later uitbreiden met jouw eigen posities.
PRICE_MAPPING_BY_ISIN: dict[str, str] = {
    # Voorbeeld: Vanguard FTSE All-World (acc, IE00BK5BQT80) op XETRA
    "IE00BK5BQT80": "VWCE.DE",
    # Future of Defence UCITS ETF (IE000OJ5TQP4), ticker ASWC op XETRA
    "IE000OJ5TQP4": "ASWC.DE",
    # Crypto ETN's - gebruik onderliggende crypto in EUR
    "XFC000A2YY6Q": "BTC-EUR",  # BITCOIN
    "XFC000A2YY6X": "ETH-EUR",  # ETHEREUM
}


def map_to_ticker(product: str | None, isin: str | None) -> str | None:
    """Bepaal de yfinance-ticker voor een positie op basis van ISIN/product."""
    # Zorg dat we strings hebben (vang NaN/None af)
    isin = str(isin).strip() if pd.notna(isin) else ""
    product = str(product).strip() if pd.notna(product) else ""

    if isin and isin in PRICE_MAPPING_BY_ISIN:
        return PRICE_MAPPING_BY_ISIN[isin]

    upper_product = product.upper()
    
    # Fallback op productnaam als ISIN ontbreekt of niet gemapt is
    if "VANGUARD FTSE ALL-WORLD" in upper_product:
        # User confirmed IE00BK5BQT80 -> VWCE
        return "VWCE.DE"
        
    if upper_product.startswith("BITCOIN"):
        return "BTC-EUR"
    if upper_product.startswith("ETHEREUM"):
        return "ETH-EUR"

    return None


@st.cache_data(ttl=30)
def fetch_tradegate_price(isin: str) -> float | None:
    """Schraap de laatste koers van Tradegate (voor real-time nauwkeurigheid)."""
    try:
        import requests
        # Tradegate Orderboek pagina
        url = f"https://www.tradegate.de/orderbuch.php?isin={isin}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code != 200:
            return None
        
        # Regex om <td id="last">123,45</td> te vinden
        # Dit is de 'Laatst' koers op de Tradegate website. 
        # We maken de regex iets flexibeler (bv. als er extra attributes zijn of spaties)
        match = re.search(r'id="last"[^>]*>\s*([\d.,]+)\s*<', resp.text)
        if match:
            # Europees formaat: 1.234,56 -> 1234.56
            price_str = match.group(1).replace(".", "").replace(",", ".")
            return float(price_str)
    except Exception:
        pass
    return None


@st.cache_data(ttl=30)
def fetch_live_prices(tickers: list[str]) -> dict[str, float]:
    """Vraag de laatste slotkoers op. Eerst Tradegate (voor Vanguard/bekende), dan YFinance."""
    if not tickers:
        return {}

    unique_tickers = sorted(list(set(t for t in tickers if t)))
    results = {}
    
    # 1. Probeer Tradegate voor stocks waar we de ISIN van weten
    ticker_to_isin = {v: k for k, v in PRICE_MAPPING_BY_ISIN.items()}
    yf_tickers = []
    
    for t in unique_tickers:
        price_found = False
        
        # Specifieke check voor ISINs in onze mapping
        if t in ticker_to_isin:
            isin = ticker_to_isin[t]
            # Crypto heeft geen Tradegate ISIN pagina die we zo makkelijk scrapen, en is 24/7 dus YF is prima
            if not isin.startswith("XFC"): 
                tg_price = fetch_tradegate_price(isin)
                if tg_price:
                    results[t] = tg_price
                    price_found = True
        
        if not price_found:
            yf_tickers.append(t)

    if not yf_tickers:
        return results

    # 2. De overgebleven tickers via YFinance (Smart Selection)
    download_list = yf_tickers[:]
    alternatives = {"VWCE.DE": ["VWCE.F", "VWCE.SG"]}
    
    for main, alts in alternatives.items():
        if main in yf_tickers:
            download_list.extend(alts)

    try:
        data = yf.download(download_list, period="1d", group_by="ticker", progress=False)
    except Exception:
        return results

    def get_latest_from_df(df_in) -> tuple[pd.Timestamp, float] | None:
        if df_in.empty or "Close" not in df_in.columns: return None
        valid = df_in["Close"].dropna()
        if valid.empty: return None
        return (valid.index[-1], float(valid.iloc[-1]))

    for t in yf_tickers:
        candidates = [t]
        if t in alternatives: candidates += alternatives[t]
        
        best_ts = None
        best_val = 0.0
        
        for cand in candidates:
            try:
                if len(download_list) == 1:
                    df_cand = data
                else:
                    if cand not in data.columns.levels[0]: continue
                    df_cand = data[cand]
                
                res = get_latest_from_df(df_cand)
                if res:
                    ts, val = res
                    if best_ts is None or ts > best_ts:
                        best_ts = ts
                        best_val = val
            except Exception: pass
        
        if best_val > 0:
            results[t] = best_val
            
    return results


@fragment(run_every=30)
def render_metrics(df: pd.DataFrame) -> None:
    """Render alleen de metrics die elke 30 sec verversen."""
    # We berekenen positions hier binnen het fragment, zodat bij een refresh 
    # de live koersen opnieuw worden opgehaald (via fetch_live_prices die dan expired is)
    positions = build_positions(df)
    
    # Live koersen en actuele waarde per positie
    if not positions.empty:
        positions["ticker"] = positions.apply(
            lambda r: map_to_ticker(r.get("product"), r.get("isin")), axis=1
        )
        price_map = fetch_live_prices(positions["ticker"].dropna().unique().tolist())
        positions["last_price"] = positions["ticker"].map(price_map)
        positions["current_value"] = positions.apply(
            lambda r: (
                r["quantity"] * r["last_price"]
                if pd.notna(r.get("last_price")) and pd.notna(r.get("quantity"))
                else pd.NA
            ),
            axis=1,
        )
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
    
    total_equity = total_market_value + current_cash
    net_invested_total = total_deposits - total_withdrawals
    total_result = total_equity - net_invested_total

    # Layout: 2 rijen van 3 kolommen zoals gevraagd
    
    # Periode weergeven
    if "value_date" in df.columns and not df["value_date"].empty:
        min_date = df["value_date"].min()
        max_date = df["value_date"].max()
        period_str = f"{min_date.strftime('%B %Y')} - {max_date.strftime('%B %Y')}"
        st.markdown(f"**Periode data:** {period_str}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Gekochte aandelen", format_eur(abs(total_buys)))
    col2.metric("Huidige marktwaarde (live)", format_eur(total_market_value))
    col3.metric("Totaal Resultaat (Winst/Verlies)", format_eur(total_result), 
               help="Berekening: (Waarde + Saldo) - (Stortingen - Opnames)")

    col4, col5, col6 = st.columns(3)
    col4.metric("Totaal aandelen verkocht", format_eur(total_sells))
    col5.metric("Totale Kosten (Transacties + Derden)", format_eur(total_fees))
    col6.metric("Ontvangen dividend", format_eur(total_dividends))


@fragment(run_every=30)
def render_overview(df: pd.DataFrame) -> None:
    """Render de open posities tabel en allocatie chart met auto-refresh."""
    positions = build_positions(df)
    
    if not positions.empty:
        positions["ticker"] = positions.apply(
            lambda r: map_to_ticker(r.get("product"), r.get("isin")), axis=1
        )
        price_map = fetch_live_prices(positions["ticker"].dropna().unique().tolist())
        positions["last_price"] = positions["ticker"].map(price_map)
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
                display["Totaal geinvesteerd"] = display["invested"].map(format_eur)
                display["Huidige waarde"] = display["current_value"].map(format_eur)
                
                # Winst/verlies berekening
                display["Winst/verlies (EUR)"] = (
                    display["current_value"] + display["net_cashflow"]
                ).map(format_eur)

                def _pl_pct(row: pd.Series) -> float | None:
                    cur = row.get("current_value")
                    net_cf = row.get("net_cashflow")
                    inv = row.get("invested")
                    if pd.notna(cur) and pd.notna(net_cf) and pd.notna(inv) and inv != 0:
                        pl_amount = cur + net_cf
                        return (pl_amount / inv) * 100.0
                    return pd.NA

                display["Winst/verlies (%)"] = display.apply(_pl_pct, axis=1).map(format_pct)
                display = display.rename(
                    columns={
                        "Display Name": "Product",
                        "isin": "ISIN",
                        "quantity": "Aantal",
                        "trades": "Transacties",
                        "ticker": "Ticker",
                    }
                )
                display = display[[
                    "Product", "Ticker", "Totaal geinvesteerd", "Huidige waarde",
                    "Winst/verlies (EUR)", "Winst/verlies (%)", "Aantal",
                    "Transacties",
                ]]
                
                # Transponeren voor mobiel: Producten worden kolommen, Metrics worden rijen
                display = display.set_index("Product").T
                st.dataframe(display, use_container_width=True, key=f"table_{cat}")

        # Portefeuilleverdeling
        alloc = positions.copy()
        alloc["alloc_value"] = alloc["current_value"].fillna(alloc["invested"])
        alloc = alloc[alloc["alloc_value"].notna() & (alloc["alloc_value"] > 0)]
        if not alloc.empty:
            st.subheader("Huidige portefeuilleverdeling")
            alloc["Display Name"] = alloc["product"].apply(_shorten_name)
            fig_alloc = px.pie(alloc, names="Display Name", values="alloc_value")
            fig_alloc.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                dragmode=False
            )
            st.plotly_chart(fig_alloc, use_container_width=True, config={'scrollZoom': False})
    else:
        st.caption("Geen open posities gevonden op basis van de transacties.")



# Function for static tables/charts that doesn't need constant refresh/reset
def render_charts(df: pd.DataFrame, history_df: pd.DataFrame, trading_volume: pd.DataFrame) -> None:
    st.markdown("---")
    tab_overview, tab_balance, tab_history, tab_transactions = st.tabs(
        ["📈 Overzicht", "💰 Saldo & Cashflow", " Historie", "📋 Transacties"]
    )

    with tab_overview:
        # Dit fragment ververst elke 30 seconden
        render_overview(df)


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
        st.subheader("Historische waardeontwikkeling (Indicatief)")
        st.markdown(
            "Hier zie je hoeveel waarde je in bezit had per week (Aantal * Koers). "
            "Dit is gebaseerd op de wekelijkse slotkoers en je transactiehistorie."
        )
        if not history_df.empty:
            products = sorted(history_df["product"].unique())
            selected_product = st.selectbox("Selecteer een product", products)
            subset = history_df[history_df["product"] == selected_product].copy()
            if not subset.empty:
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                fig_hist = make_subplots(specs=[[{"secondary_y": True}]])
                # Default view range: 1 Month
                end_date = pd.Timestamp.now()
                start_date_1m = end_date - pd.DateOffset(months=1)

                fig_hist.add_trace(go.Scatter(x=subset["date"], y=subset["value"], name="Waarde in bezit (EUR)", mode='lines', connectgaps=True, line=dict(color="#636EFA")), secondary_y=False)
                fig_hist.add_trace(go.Scatter(x=subset["date"], y=subset["price"], name="Koers (EUR)", mode='lines', connectgaps=True, line=dict(color="#EF553B", dash='dot')), secondary_y=True)
                
                # Removed manual range calculation to allow autoscaling
                fig_hist.update_yaxes(title_text="Totale Waarde (€)", secondary_y=False, showgrid=True)
                fig_hist.update_yaxes(title_text="Koers per aandeel (€)", secondary_y=True, showgrid=False)
                
                fig_hist.update_layout(
                    title_text=f"Historie voor {selected_product}", hovermode="x unified",
                    legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255, 255, 255, 0)"),
                    xaxis=dict(
                        range=[start_date_1m, end_date],  # Default 1M view
                        rangeslider=dict(visible=False), 
                        type="date",
                        rangeselector=dict(
                            buttons=list([
                                dict(count=1, label="1d", step="day", stepmode="backward"),
                                dict(count=7, label="1w", step="day", stepmode="backward"),
                                dict(count=1, label="1m", step="month", stepmode="backward"),
                                dict(count=3, label="3m", step="month", stepmode="backward"),
                                dict(count=6, label="6m", step="month", stepmode="backward"),
                                dict(count=1, label="1y", step="year", stepmode="backward"),
                                dict(count=5, label="5y", step="year", stepmode="backward"),
                                dict(step="all"),
                                dict(count=1, label="YTD", step="year", stepmode="todate"),
                            ])
                        )
                    ),
                    dragmode=False
                )
                # Bereken 15% padding voor de assen voor een mooiere look -- REMOVED for autoscaling
                # val_min, val_max = subset["value"].min(), subset["value"].max()
                # val_range = max(val_max - val_min, 1.0)
                # val_lims = [val_min - 0.15 * val_range, val_max + 0.15 * val_range]
                
                # price_min, price_max = subset["price"].min(), subset["price"].max()
                # price_range = max(price_max - price_min, 1.0)
                # price_lims = [price_min - 0.15 * price_range, price_max + 0.15 * price_range]

                fig_hist.update_yaxes(title_text="Totale Waarde (€)", secondary_y=False, type="linear", showgrid=True)
                fig_hist.update_yaxes(title_text="Koers per aandeel (€)", secondary_y=True, type="linear", showgrid=False)
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
                    # Pas naamverkorting toe voor de legenda
                    compare_df["product"] = compare_df["product"].apply(_shorten_name)
                    
                    fig_compare = px.line(
                        compare_df, x="date", y="value", color="product", 
                        title="Waarde per aandeel in de tijd (EUR)", 
                        labels={"value": "Waarde (EUR)", "date": "Datum", "product": "Product"}
                    )
                
                # Bereken 15% padding voor de y-as -- REMOVED for autoscaling
                # y_min, y_max = compare_df["value"].min(), compare_df["value"].max()
                # y_range = max(y_max - y_min, 1.0)
                # y_lims = [y_min - 0.15 * y_range, y_max + 0.15 * y_range]
                
                fig_compare.update_layout(
                    legend=dict(orientation="h", yanchor="top", y=-0.4, xanchor="left", x=0),
                    # yaxis=dict(range=y_lims),
                    xaxis=dict(
                        range=[start_date_1m, end_date],  # Default 1M view
                        rangeslider=dict(visible=False), 
                        type="date",
                        rangeselector=dict(
                            buttons=list([
                                dict(count=1, label="1d", step="day", stepmode="backward"),
                                dict(count=7, label="1w", step="day", stepmode="backward"),
                                dict(count=1, label="1m", step="month", stepmode="backward"),
                                dict(count=3, label="3m", step="month", stepmode="backward"),
                                dict(count=6, label="6m", step="month", stepmode="backward"),
                                dict(count=1, label="1y", step="year", stepmode="backward"),
                                dict(count=5, label="5y", step="year", stepmode="backward"),
                                dict(step="all"),
                                dict(count=1, label="YTD", step="year", stepmode="todate"),
                            ])
                        )
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

    df = enrich_transactions(df_raw)
    positions = build_positions(df)
    trading_volume = build_trading_volume_by_month(df)
    history_df = build_portfolio_history(df)
    
    render_metrics(df)
    render_charts(df, history_df, trading_volume)


if __name__ == "__main__":
    main()


