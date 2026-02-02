import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def format_eur(value: float) -> str:
    """Format a float as European-style euro string."""
    if pd.isna(value):
        return "€ 0,00"
    # First format with US/UK style, then swap separators
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"


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
    if "DEGIRO Transactiekosten" in desc:
        return "Fee"
    if "Dividendbelasting" in desc:
        return "Dividend Tax"
    if "Dividend" in desc:
        return "Dividend"
    if "Flatex Interest Income" in desc:
        return "Interest"
    if "iDEAL Deposit" in desc:
        return "Deposit"
    if "Reservation iDEAL" in desc:
        return "Reservation"
    if "Overboeking van uw geldrekening" in desc:
        return "Deposit"
    if "Overboeking naar uw geldrekening" in desc:
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
    """Bepaal open posities per product op basis van trades."""
    if "product" not in df.columns:
        return pd.DataFrame()

    trades = df[df["is_trade"]].copy()
    if trades.empty:
        return pd.DataFrame()

    grouped = (
        trades.groupby(["product", "isin"], dropna=False)
        .agg(
            quantity=("quantity", "sum"),
            invested=("buy_cash", lambda s: -s.sum()),
            realized_pnl=("sell_cash", "sum"),
            trades=("amount", "count"),
        )
        .reset_index()
    )

    # Alleen nog posities met resterende stukken tonen
    grouped = grouped[grouped["quantity"].round(8) != 0]
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


def main() -> None:
    st.set_page_config(
        page_title="DeGiro Portfolio Dashboard",
        layout="wide",
    )

    st.title("DeGiro Portfolio Dashboard")
    st.markdown(
        "Upload je **DeGiro Account.csv** export of gebruik het voorbeeldbestand om "
        "een aantal basisinzichten over je portefeuille te krijgen. "
        "De cijfers zijn gebaseerd op de transacties, vergelijkbaar met wat tools als "
        "Portfolio Performance tonen (cashflows, posities, kosten, dividend)."
    )

    sidebar = st.sidebar
    sidebar.header("Instellingen")

    uploaded_file = sidebar.file_uploader(
        "Upload een DeGiro CSV-bestand",
        type=["csv"],
        help="Gebruik bij voorkeur de 'Account.csv' export uit DeGiro.",
    )

    use_example = sidebar.checkbox(
        "Gebruik voorbeelddata (Account_year.csv)", value=uploaded_file is None
    )

    df_raw: pd.DataFrame | None = None

    if uploaded_file is not None:
        df_raw = load_degiro_csv(uploaded_file)
    elif use_example:
        example_path = Path(__file__).with_name("Account_year.csv")
        if example_path.exists():
            df_raw = load_degiro_csv(example_path)
        else:
            st.warning(
                "Voorbeeldbestand `Account_year.csv` niet gevonden in de huidige map."
            )

    if df_raw is None:
        st.info("Upload een CSV-bestand of schakel de voorbeelddata in via de sidebar.")
        return

    df = enrich_transactions(df_raw)
    positions = build_positions(df)
    cashflow_monthly = build_cashflow_by_month(df)
    balance_series = build_balance_series(df)

    # Globale samenvatting
    total_deposits = df.loc[df["type"] == "Deposit", "amount"].sum()
    total_withdrawals = -df.loc[df["type"] == "Withdrawal", "amount"].sum()
    total_fees = -df.loc[df["is_fee"], "amount"].sum()
    total_dividends = df.loc[df["is_dividend"], "amount"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totaal gestort", format_eur(total_deposits))
    col2.metric("Totaal opgenomen", format_eur(total_withdrawals))
    col3.metric("Transactiekosten", format_eur(total_fees))
    col4.metric("Ontvangen dividend", format_eur(total_dividends))

    st.markdown("---")

    tab_overview, tab_positions, tab_transactions, tab_costs = st.tabs(
        ["📈 Overzicht", "📊 Posities", "📋 Transacties", "💶 Kosten & Dividend"]
    )

    with tab_overview:
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

    with tab_positions:
        st.subheader("Open posities (afgeleid uit koop/verkoop-transacties)")
        if not positions.empty:
            display = positions.copy()
            display["Geïnvesteerd"] = display["invested"].map(format_eur)
            display["Gerealiseerde P/L (cash)"] = display["realized_pnl"].map(
                format_eur
            )
            display = display.rename(
                columns={
                    "product": "Product",
                    "isin": "ISIN",
                    "quantity": "Aantal",
                    "trades": "Aantal transacties",
                }
            )
            st.dataframe(display, use_container_width=True)
        else:
            st.caption("Geen open posities gevonden op basis van de transacties.")

    with tab_transactions:
        st.subheader("Ruwe transactiedata")
        st.dataframe(df, use_container_width=True, height=500)

    with tab_costs:
        st.subheader("Overzicht kosten")
        fees = df[df["is_fee"]].copy()
        if not fees.empty:
            fees_by_product = (
                fees.groupby("product")["amount"].sum().reset_index(name="fees")
            )
            fees_by_product["fees_abs"] = -fees_by_product["fees"]
            fig_fees = px.bar(
                fees_by_product.sort_values("fees_abs", ascending=False),
                x="product",
                y="fees_abs",
                labels={"product": "Product", "fees_abs": "Kosten (EUR)"},
            )
            st.plotly_chart(fig_fees, use_container_width=True)
        else:
            st.caption("Geen transactiekosten gevonden in deze dataset.")

        st.subheader("Dividend en dividendbelasting")
        div = df[df["is_dividend"] | df["is_tax"]].copy()
        if not div.empty:
            div_by_product = (
                div.groupby(["product", "type"])["amount"]
                .sum()
                .reset_index(name="amount")
            )
            fig_div = px.bar(
                div_by_product,
                x="product",
                y="amount",
                color="type",
                labels={
                    "product": "Product",
                    "amount": "Bedrag (EUR)",
                    "type": "Type",
                },
                barmode="group",
            )
            st.plotly_chart(fig_div, use_container_width=True)
        else:
            st.caption("Geen dividend- of dividendbelastingtransacties gevonden.")


if __name__ == "__main__":
    main()
