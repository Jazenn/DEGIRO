import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees CSV met flexibele separator
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=None, engine="python")
    
    st.subheader("📊 Portfolio Inzichten")
    
    # Normaliseer kolomnamen en converteer NL getallen
    cols_lower = {col.lower(): col for col in df.columns}
    
    # Datum, Mutatie, Saldo, Product kolommen vinden
    date_col = cols_lower.get('datum', None)
    product_col = cols_lower.get('product', None)
    mutatie_col = cols_lower.get('mutatie', None)
    saldo_col = cols_lower.get('saldo', None)
    
    if date_col:
        df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.sort_values('__date')
    
    # NL nummers -> float (1.000,00 -> 1000.00)
    def nl_to_float(series):
        return (series.astype(str)
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
                .astype(float))
    
    if mutatie_col:
        df['mutatie_num'] = nl_to_float(df[mutatie_col])
    if saldo_col:
        df['saldo_num'] = nl_to_float(df[saldo_col])
    
    # === COL1: KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_mut = df['mutatie_num'].sum() if 'mutatie_num' in df else 0
        st.metric("💰 Totale mutatie", f"€{total_mut:,.0f}")
    
    with col2:
        if saldo_col and 'saldo_num' in df:
            last_saldo = df['saldo_num'].iloc[-1]
            st.metric("🏦 Laatste saldo", f"€{last_saldo:,.0f}")
    
    with col3:
        stortingen = df[df['mutatie_num'] > 0]['mutatie_num'].sum()
        st.metric("📈 Stortingen", f"€{stortingen:,.0f}")
    
    with col4:
        transactiekosten = df[df[mutatie_col].str.contains('kosten|transactiekosten', case=False, na=False)]['mutatie_num'].sum()
        st.metric("💸 Transactiekosten", f"€{abs(transactiekosten):,.0f}")
    
    # === COL2: Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Saldo over tijd")
        if 'saldo_num' in df and '__date' in df:
            saldo_data = df.dropna(subset=['__date', 'saldo_num'])
            if not saldo_data.empty:
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.plot(saldo_data['__date'], saldo_data['saldo_num'], linewidth=2, marker='o')
                ax.set_title('Saldo verloop')
                ax.set_xlabel('Datum')
                ax.set_ylabel('Saldo (€)')
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Transacties per product")
        if product_col:
            top_products = df[product_col].value_counts().head(8)
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(top_products.values, labels=top_products.index, autopct='%1.1f%%')
            ax.set_title('Verdeling transacties per product')
            st.pyplot(fig)
    
    # === Posities per product ===
    st.markdown("### 📋 Huidige posities (gebaseerd op producten)")
    if product_col:
        positions = df[df['mutatie_num'] < 0].groupby(product_col)['mutatie_num'].sum().sort_values()
        st.dataframe(positions)
    
    # === Transacties tabel ===
    st.markdown("### 📄 Laatste 20 transacties")
    display_cols = [date_col, product_col, mutatie_col, saldo_col] if all(c in df.columns for c in [date_col, product_col, mutatie_col, saldo_col]) else None
    if display_cols:
        st.dataframe(df[display_cols].tail(20))
    else:
        st.dataframe(df.tail(20))
    
else:
    st.info("👆 Upload je DEGIRO CSV bestand om te beginnen!")
    st.markdown("""
    ### 💡 Wat doet deze app?
    - Toont **saldo verloop** over tijd
    - Geeft **KPI's** zoals stortingen en kosten
    - Maakt een **pie chart** van je producten
    - Geeft overzicht van je **posities**
    """)
