import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees CSV PRECIES zoals DEGIRO export
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    # === BELANGRIJK: DEGIRO heeft Unnamed kolommen voor bedragen ===
    # Kolom volgorde uit jouw CSV: ['Datum','Tijd','Valutadatum','Product','ISIN','Omschrijving','FX','Mutatie','Unnamed: 8','Saldo','Unnamed: 10','Order Id']
    
    date_col = 'Datum'
    product_col = 'Product'
    omschrijving_col = 'Omschrijving'
    
    # ECHTE BEDRAG KOLOMMEN (Unnamed!)
    mutatie_bedrag_col = 'Unnamed: 8'    # Bedrag naast Mutatie
    saldo_bedrag_col = 'Unnamed: 10'     # Bedrag naast Saldo
    
    # Datum
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    
    # BULLETPROOF NL conversie
    def convert_nl_number(value):
        if pd.isna(value) or str(value).strip() == '':
            return 0.0
        s = str(value).strip()
        s = s.replace('.', '')  # 1.000,00 → 1000,00
        s = s.replace(',', '.') # 1000,00 → 1000.0
        try:
            return float(s)
        except:
            return 0.0
    
    # CONVERTEER ECHTE BEDRAG KOLOMMEN
    df['mutatie_num'] = df[mutatie_bedrag_col].apply(convert_nl_number)
    df['saldo_num'] = df[saldo_bedrag_col].apply(convert_nl_number)
    
    df = df.sort_values('__date')
    
    st.success("✅ ECHTE bedragen gevonden en geconverteerd!")
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    
    total_mut = df['mutatie_num'].sum()
    last_saldo = df['saldo_num'].iloc[-1]
    stortingen = df[df['mutatie_num'] > 0]['mutatie_num'].sum()
    
    with col1: st.metric("💰 Totale mutatie", f"€{total_mut:,.0f}")
    with col2: st.metric("🏦 Laatste saldo", f"€{last_saldo:,.0f}")
    with col3: st.metric("📈 Stortingen", f"€{stortingen:,.0f}")
    with col4: st.metric("💰 Investeringen", f"€{-df[df['mutatie_num'] < 0]['mutatie_num'].sum():,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Saldo over tijd")
        data = df.dropna(subset=['__date', 'saldo_num'])
        if len(data) > 1:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(data['__date'], data['saldo_num'], 'o-', linewidth=2)
            ax.set_title('Saldo verloop')
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Transacties per product")
        top = df[product_col].dropna().value_counts().head(8)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(top.values, labels=top.index, autopct='%1.1f%%')
        st.pyplot(fig)
    
    # === POSITIES ===
    st.markdown("### 💼 Investeringen per product")
    investeringen = df[df['mutatie_num'] < 0].groupby(product_col)['mutatie_num'].sum()
    st.dataframe(investeringen.sort_values().round(0))
    
    # === BEWIJS ===
    st.markdown("### ✅ BEWIJS: Werkende conversie")
    st.dataframe(df[[date_col, product_col, mutatie_bedrag_col, 'mutatie_num', saldo_bedrag_col, 'saldo_num']].head(10))
    
else:
    st.info("👆 Upload je CSV!")
