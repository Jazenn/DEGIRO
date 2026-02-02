import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import dateutil.parser  # Voor flexibele datumparsing

st.set_page_config(page_title="DEGIRO Inzichten", layout="wide")

st.title("🧠 DEGIRO Account Inzichten")
st.markdown("Upload je DEGIRO rekeningoverzicht CSV voor analyses.")

# File uploader
uploaded_file = st.file_uploader("Kies een DEGIRO CSV-bestand", type="csv")

if uploaded_file is not None:
    @st.cache_data
    def load_data(file):
        # Probeer veelvoorkomende encodings en separators voor DEGIRO CSV
        try:
            df = pd.read_csv(file, sep=';', encoding='utf-8')  # DEGIRO vaak semicolon
        except:
            try:
                df = pd.read_csv(file, sep=',', encoding='latin1')
            except:
                df = pd.read_csv(file, sep=';', encoding='latin1')
        return df

    df = load_data(uploaded_file)
    st.success(f"✅ Geladen: {len(df)} transacties.")

    # Kolomnamen tonen en aanpassen (typisch DEGIRO kolommen)
    st.subheader("📊 Data Voorbeeld")
    st.dataframe(df.head())

    # Kolommen detecteren/mappen (flexibel voor variaties)
    col_date = next((col for col in df.columns if any(x in col.lower() for x in ['datum', 'date', 'tijd'])), df.columns[0])
    col_product = next((col for col in df.columns if any(x in col.lower() for x in ['product', 'isin'])), None)
    col_quantity = next((col for col in df.columns if 'aantal' in col.lower() or 'quantity' in col.lower()), None)
    col_price = next((col for col in df.columns if 'koers' in col.lower() or 'price' in col.lower()), None)
    col_value = next((col for col in df.columns if any(x in col.lower() for x in ['waarde', 'value', 'total', 'totaal'])), None)

    if col_date and col_product and col_quantity and col_value:
        # Datum parsen
        df['Datum'] = pd.to_datetime(df[col_date].astype(str), errors='coerce', dayfirst=True)
        df['Product'] = df[col_product].fillna('')
        df['Quantity'] = pd.to_numeric(df[col_quantity], errors='coerce')
        df['Value_EUR'] = pd.to_numeric(df[col_value].str.replace(',', '.'), errors='coerce')  # Komma naar punt voor decimalen

        # Tabs voor inzichten
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Transacties", "💼 Holdings", "📊 Grafieken", "💰 Samenvatting"])

        with tab1:
            st.subheader("Transacties Overzicht")
            filtered_df = df[['Datum', 'Product', 'Quantity', 'Value_EUR']].dropna(subset=['Datum'])
            st.dataframe(filtered_df.sort_values('Datum', ascending=False))

        with tab2:
            st.subheader("Huidige Holdings")
            holdings = df.groupby('Product')['Quantity'].sum().reset_index()
            holdings['Totaal_Waarde'] = 0  # Placeholder; voor echte waarde heb je huidige prijzen nodig
            st.dataframe(holdings[holdings['Quantity'] != 0].sort_values('Quantity', key=abs, ascending=False))

        with tab3:
            st.subheader("Visualisaties")
            fig = px.bar(df, x='Product', y='Value_EUR', color='Quantity', title="Transacties per Product")
            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.line(df, x='Datum', y='Value_EUR', color='Product', title="Cumulatieve Waarde Over Tijd")
            st.plotly_chart(fig2, use_container_width=True)

        with tab4:
            st.subheader("Key Metrics")
            total_invested = df['Value_EUR'].sum()
            avg_transaction = df['Value_EUR'].mean()
            num_trades = len(df)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Totaal Transacties", num_trades)
            with col2:
                st.metric("Gemiddelde Transactie", f"€{avg_transaction:,.2f}")
            with col3:
                st.metric("Totale Omzet", f"€{total_invested:,.2f}")

    else:
        st.warning("⚠️ Kan geen standaard DEGIRO-kolommen detecteren. Controleer je CSV-koppen en probeer opnieuw.")
        st.info("Typische kolommen: Datum/Tijd, Product/ISIN, Aantal, Koers, Waarde EUR, Totaal EUR.[web:3][web:4]")

else:
    st.info("👆 Upload je DEGIRO CSV om te beginnen.")
