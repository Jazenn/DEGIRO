import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees DEGIRO CSV correct
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    # DEGIRO kolom volgorde
    date_col = 'Datum'
    product_col = 'Product'
    omschrijving_col = 'Omschrijving'
    mutatie_bedrag_col = 'Unnamed: 8'  # Echte bedragen!
    saldo_bedrag_col = 'Unnamed: 10'
    
    # Datum
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    
    # NL conversie
    def convert_nl_number(value):
        if pd.isna(value) or str(value).strip() == '':
            return 0.0
        s = str(value).strip().replace('.', '').replace(',', '.')
        try:
            return float(s)
        except:
            return 0.0
    
    df['bedrag'] = df[mutatie_bedrag_col].apply(convert_nl_number)
    df['saldo_num'] = df[saldo_bedrag_col].apply(convert_nl_number)
    
    # === FILTER: ALLEEN BELANGRIJKE TRANSACTIES ===
    ignore_types = [
        'ideal deposit', 'reservation ideal', 'degiro cash sweep', 
        'overboeking naar', 'overboeking van', 'flatex interest'
    ]
    
    # Filter transacties (geen cash movements)
    mask_relevant = True
    for ignore in ignore_types:
        mask_relevant &= ~df[omschrijving_col].astype(str).str.contains(ignore, case=False, na=False)
    
    df_relevant = df[mask_relevant].copy()
    
    # === PORTFOLIO LOGICA ===
    # Koop = negatief bedrag → POSITIEVE portefeuille waarde
    df_relevant['portefeuille_waarde'] = 0.0
    df_relevant.loc[df_relevant['bedrag'] < 0, 'portefeuille_waarde'] = -df_relevant['bedrag']
    
    # Kosten zijn meestal negatief klein
    df_relevant['is_kosten'] = df_relevant[omschrijving_col].astype(str).str.contains('kosten|transactiekosten|fee', case=False, na=False)
    
    # Dividend = positief klein
    df_relevant['is_dividend'] = df_relevant[omschrijving_col].astype(str).str.contains('dividend', case=False, na=False)
    
    st.success("✅ Transacties gefilterd & portefeuille berekend!")
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    
    totale_investering = df_relevant['portefeuille_waarde'].sum()
    totale_kosten = df_relevant[df_relevant['is_kosten']]['bedrag'].sum()
    totaal_dividend = df_relevant[df_relevant['is_dividend']]['bedrag'].sum()
    laatste_saldo = df['saldo_num'].iloc[-1]
    
    with col1: st.metric("💼 Totale investering", f"€{totale_investering:,.0f}")
    with col2: st.metric("💸 Totale kosten", f"€{abs(totale_kosten):,.0f}")
    with col3: st.metric("💰 Dividend ontvangen", f"€{totaal_dividend:,.0f}")
    with col4: st.metric("🏦 Laatste saldo", f"€{laatste_saldo:,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Saldo over tijd")
        data = df.dropna(subset=['__date', 'saldo_num'])
        if len(data) > 1:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(data['__date'], data['saldo_num'], 'o-', linewidth=2, label='Cash saldo')
            ax.plot(df_relevant['__date'], df_relevant['portefeuille_waarde'].cumsum(), 'r--', 
                   linewidth=2, label='Portefeuille groei')
            ax.legend()
            ax.set_title('Cash + Portefeuille verloop')
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Investering per product")
        portfolio_by_product = df_relevant[df_relevant['portefeuille_waarde'] > 0].groupby(product_col)['portefeuille_waarde'].sum()
        if len(portfolio_by_product) > 0:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(portfolio_by_product.values, labels=portfolio_by_product.index, autopct='%1.1f%%')
            ax.set_title('Portefeuille verdeling')
            st.pyplot(fig)
    
    # === POSITIES ===
    st.markdown("### 💼 Huidige posities")
    positions = df_relevant[df_relevant['portefeuille_waarde'] > 0].groupby(product_col)['portefeuille_waarde'].sum()
    st.dataframe(positions.sort_values(ascending=False).round(0))
    
    # === TRANSACTIES ===
    st.markdown("### 📋 Laatste relevante transacties")
    display_cols = [date_col, product_col, omschrijving_col, mutatie_bedrag_col, 'bedrag', 'portefeuille_waarde']
    st.dataframe(df_relevant[display_cols].sort_values('__date', ascending=False).head(15))
    
else:
    st.info("👆 Upload je CSV!")
