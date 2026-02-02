import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf


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

    # Parse dates (European format)
    if "value_date" in df.columns:
        df["value_date"] = pd.to_datetime(
            df["value_date"], format="%d-%m-%Y", errors="coerce"
        )
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")

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


def build_cashflow_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Netto in-/uitstroom per maand."""
    if "value_date" not in df.columns:
        return pd.DataFrame()

    cash = df[df["is_cashflow"]].copy()
    if cash.empty:
        return pd.DataFrame()

    cash["month"] = cash["value_date"].dt.to_period("M").dt.to_timestamp()
    monthly = cash.groupby("month")["amount"].sum().reset_index(name="net_cashflow")
    return monthly


def build_balance_series(df: pd.DataFrame) -> pd.DataFrame:
    """Reeks van kassaldo in de tijd."""
    if "balance" not in df.columns or "value_date" not in df.columns:
        return pd.DataFrame()

    bal = df.dropna(subset=["balance", "value_date"]).copy()
    if bal.empty:
        return pd.DataFrame()

    bal = bal.sort_values("value_date")
    bal = bal[["value_date", "balance"]]
    return bal


# Eenvoudige mapping van ISIN/product naar een yfinance-ticker.
# Dit kun je later uitbreiden met jouw eigen posities.
PRICE_MAPPING_BY_ISIN: dict[str, str] = {
    # Voorbeeld: Vanguard FTSE All-World (acc, IE00BK5BQT80) op XETRA
    "IE00BK5BQT80": "VWCE.DE",
    # Future of Defence UCITS ETF (IE000OJ5TQP4), ticker ASWC op XETRA
    "IE000OJ5TQP4": "ASWC.DE",
    # Aegon op Euronext Amsterdam
    "BMG0112X1056": "AGN.AS",
    # Crypto ETN's - gebruik onderliggende crypto in EUR
    "XFC000A2YY6Q": "BTC-EUR",  # BITCOIN
    "XFC000A2YY6X": "ETH-EUR",  # ETHEREUM
}


def map_to_ticker(product: str | None, isin: str | None) -> str | None:
    """Bepaal de yfinance-ticker voor een positie op basis van ISIN/product."""
    isin = (isin or "").strip()
    product = (product or "").strip()

    if isin and isin in PRICE_MAPPING_BY_ISIN:
        return PRICE_MAPPING_BY_ISIN[isin]

    upper_product = product.upper()
    if upper_product.startswith("BITCOIN"):
        return "BTC-EUR"
    if upper_product.startswith("ETHEREUM"):
        return "ETH-EUR"

    return None


def fetch_live_prices(tickers: list[str]) -> dict[str, float]:
    """Vraag de laatste slotkoers op per ticker via yfinance."""
    prices: dict[str, float] = {}
    for ticker in sorted({t for t in tickers if t}):
        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                prices[ticker] = float(data["Close"].iloc[-1])
        except Exception:
            # Bij fout gewoon overslaan, zodat de rest blijft werken
            continue
    return prices


def main() -> None:
    st.set_page_config(
        page_title="DeGiro Portfolio Dashboard",
        layout="wide",
    )

    st.title("DeGiro Portfolio Dashboard")
    st.markdown(
        "Upload je **DeGiro Account.csv** om "
        "een aantal basisinzichten over je portefeuille te krijgen. "
    )

    sidebar = st.sidebar
    sidebar.header("Instellingen")

    uploaded_file = sidebar.file_uploader(
        "Upload een DeGiro CSV-bestand",
        type=["csv"],
        help="Gebruik bij voorkeur de 'Account.csv' export uit DeGiro.",
    )

    if uploaded_file is None:
        st.info("Upload een DeGiro CSV-bestand om je portefeuille te analyseren.")
        return

    df_raw = load_degiro_csv(uploaded_file)

    df = enrich_transactions(df_raw)
    positions = build_positions(df)
    cashflow_monthly = build_cashflow_by_month(df)
    balance_series = build_balance_series(df)

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
    total_fees = -df.loc[df["is_fee"], "amount"].sum()
    total_dividends = df.loc[df["is_dividend"], "amount"].sum()
    
    total_market_value = (
        positions["current_value"].dropna().sum() if not positions.empty else 0.0
    )
    
    # Bepaal huidig saldo uit de laatste regel van balance_series
    current_cash = 0.0
    if not balance_series.empty:
        current_cash = balance_series.iloc[-1]["balance"]
    
    # Totaal eigen vermogen = Marktwaarde + Cash
    total_equity = total_market_value + current_cash
    
    # Netto inleg = Stortingen - Opnames
    net_invested_total = total_deposits - total_withdrawals
    
    # Totaal resultaat = Eigen Vermogen Nu - Netto Inleg
    # Dit omvat dus ALLES: koerswinst, dividenden, kosten, rente, etc.
    total_result = total_equity - net_invested_total

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totaal gestort", format_eur(total_deposits))
    col2.metric("Totaal opgenomen", format_eur(total_withdrawals))
    col3.metric("Totale Kosten (Transacties + Derden)", format_eur(total_fees))
    col4.metric("Ontvangen dividend", format_eur(total_dividends))

    col5, col6 = st.columns(2)
    col5.metric("Huidige marktwaarde (live)", format_eur(total_market_value))
    col6.metric("Totaal Resultaat (Winst/Verlies)", format_eur(total_result))

    st.markdown("---")

    tab_overview, tab_balance, tab_transactions = st.tabs(
        ["📈 Overzicht", "� Saldo & Cashflow", "📋 Transacties"]
    )

    with tab_overview:
        st.subheader("Open posities (afgeleid uit koop/verkoop-transacties)")
        if not positions.empty:
            display = positions.copy()
            # Totale aankoopkosten (bruto, zonder fees) en huidige marktwaarde
            display["Totaal geinvesteerd"] = display["invested"].map(format_eur)
            display["Huidige waarde"] = display["current_value"].map(format_eur)

            # Winst/verlies (Totaal) = Huidige Waarde + Netto Cashflow (historisch saldo van buys/sells/fees/divs)
            # Voorbeeld: Buy -1000, Fee -2, Div +10. Net Cashflow = -992. Value = 1100. P/L = 1100 - 992 = 108.
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

            display["Winst/verlies (%)"] = display.apply(_pl_pct, axis=1).map(
                format_pct
            )
            display = display.rename(
                columns={
                    "product": "Product",
                    "isin": "ISIN",
                    "quantity": "Aantal",
                    "trades": "Aantal transacties",
                    "ticker": "Ticker",
                }
            )
            # Alleen de meest relevante kolommen tonen
            display = display[
                [
                    "Product",
                    "Totaal geinvesteerd",
                    "Huidige waarde",
                    "Winst/verlies (EUR)",
                    "Winst/verlies (%)",
                    "Aantal",
                    "Aantal transacties",
                    "Ticker",
                ]
            ]
            st.dataframe(display, use_container_width=True, hide_index=True)

            # Pie chart met huidige verdeling van de portefeuille
            alloc = positions.copy()
            alloc["alloc_value"] = alloc["current_value"]
            alloc["alloc_value"] = alloc["alloc_value"].fillna(alloc["invested"])
            alloc = alloc[alloc["alloc_value"].notna() & (alloc["alloc_value"] > 0)]
            if not alloc.empty:
                st.subheader("Huidige portefeuilleverdeling")
                fig_alloc = px.pie(
                    alloc,
                    names="product",
                    values="alloc_value",
                )
                st.plotly_chart(fig_alloc, use_container_width=True)
        else:
            st.caption("Geen open posities gevonden op basis van de transacties.")

    with tab_balance:
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Kassaldo in de tijd")
            if not balance_series.empty:
                fig_bal = px.line(
                    balance_series,
                    x="value_date",
                    y="balance",
                    labels={"value_date": "Datum", "balance": "Saldo (EUR)"},
                )
                st.plotly_chart(fig_bal, use_container_width=True)
            else:
                st.caption("Geen saldo-informatie beschikbaar in dit bestand.")

        with col_b:
            st.subheader("Netto in-/uitstroom per maand")
            if not cashflow_monthly.empty:
                fig_cf = px.bar(
                    cashflow_monthly,
                    x="month",
                    y="net_cashflow",
                    labels={"month": "Maand", "net_cashflow": "Netto cashflow (EUR)"},
                )
                st.plotly_chart(fig_cf, use_container_width=True)
            else:
                st.caption("Geen cashflow-transacties gevonden.")

    with tab_transactions:
        st.subheader("Ruwe transactiedata")
        st.dataframe(df, use_container_width=True, height=500)


if __name__ == "__main__":
    main()
