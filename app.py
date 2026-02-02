import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="📈 DeGiro Portfolio Dashboard", layout="wide")
st.title("📈 DeGiro Portfolio Dashboard")

st.write("""
Upload hier je DeGiro exportbestand (CSV of TXT).
""")

uploaded_file = st.file_uploader("", accept_multiple_files=False)

if uploaded_file is not None:
    # Data inlezen
    df = pd.read_csv(uploaded_file)

    # Kolommen checken
    if 'Datum' not in df.columns or 'Mutatie' not in df.columns:
        st.error("CSV mist vereiste kolommen zoals 'Datum' of 'Mutatie'.")
    else:
        # Datum omzetten
        df['Datum'] = pd.to_datetime(df['Datum'], format='%d-%m-%Y', errors='coerce')
        df = df.sort_values('Datum')

        # Mutatie omzetten naar numeriek
        df['Mutatie'] = df['Mutatie'].astype(str).str.replace('.', '', regex=False)
        df['Mutatie'] = df['Mutatie'].str.replace(',', '.', regex=False)
        df['Mutatie'] = pd.to_numeric(df['Mutatie'], errors='coerce')

        # Netto cumulatief
        df['Cumulatief'] = df['Mutatie'].cumsum()

        st.subheader("📌 Samenvatting")
        totaal_gestort = df[df['Mutatie'] > 0]['Mutatie'].sum()
        totaal_opgenomen = abs(df[df['Mutatie'] < 0]['Mutatie'].sum())
        netto_resultaat = df['Mutatie'].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Totaal Gestort", f"€ {totaal_gestort:,.2f}")
        col2.metric("Totaal Opgenomen", f"€ {totaal_opgenomen:,.2f}")
        col3.metric("Netto Resultaat", f"€ {netto_resultaat:,.2f}")

        # Portfolio waarde over tijd (Aantal x Koers)
        if 'Aantal' in df.columns and 'Koers' in df.columns:
            df['Waarde'] = df['Aantal'] * df['Koers']
            portfolio_per_datum = df.groupby('Datum')['Waarde'].sum().reset_index()

            st.subheader("📊 Portfolio Waarde Over Tijd")
            fig_value = px.line(portfolio_per_datum, x='Datum', y='Waarde', title='Portfolio Ontwikkeling')
            st.plotly_chart(fig_value, use_container_width=True)

            # Rendement berekenen
            portfolio_per_datum['Rendement'] = portfolio_per_datum['Waarde'].pct_change() * 100
            st.subheader("📈 Rendement Over Tijd (%)")
            fig_return = px.line(portfolio_per_datum, x='Datum', y='Rendement', title='Rendement Over Tijd (%)')
            st.plotly_chart(fig_return, use_container_width=True)

        # Asset allocatie per sector
        if 'Sector' in df.columns and 'Waarde' in df.columns:
            df_sector = df.groupby('Sector')['Waarde'].sum().reset_index()
            st.subheader("🥧 Asset Allocatie per Sector")
            fig_sector = px.pie(df_sector, names='Sector', values='Waarde', title='Asset Allocatie per Sector')
            st.plotly_chart(fig_sector, use_container_width=True)

        # Dividend overzicht
        if 'Type' in df.columns:
            dividends = df[df['Type'].str.contains('Dividend', case=False, na=False)]
            if not dividends.empty:
                dividends_per_datum = dividends.groupby('Datum')['Mutatie'].sum().reset_index()
                st.subheader("💰 Dividend Inkomsten")
                fig_div = px.bar(dividends_per_datum, x='Datum', y='Mutatie', title='Dividend Inkomsten')
                st.plotly_chart(fig_div, use_container_width=True)

        # Originele transacties tonen
        st.subheader("📄 Volledige Transacties")
        st.dataframe(df)

else:
    st.info("Upload eerst je DeGiro exportbestand om te beginnen.")
