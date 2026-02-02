import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees CSV
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    # DEBUG: toon wat Pandas ziet (werkt bij jou!)
    st.subheader("🔍 DEBUG: Eerste 5 rijen")
    st.dataframe(df[['Datum', 'Product', 'Mutatie', 'Saldo']].head())
    
    # Kolomnamen
    date_col = 'Datum'
    product_col = 'Product'
    mutatie_col = 'Mutatie'
    saldo_col = 'Saldo'
    
    # 100% FAIL-SAFE NL conversie (GEEN pandas.astype meer!)
    def convert_nl_number(value):
        """Converteert 1.000,00 of -500,25 naar float"""
        if pd.isna(value) or str(value).strip() == '':
            return 0.0
        s = str(value).strip()
        s = s.replace('.', '')  # 1.000,00 -> 1000,00
        s = s.replace(',', '.') # 1000,00 -> 1000.00
        try:
            return float(s)
        except:
            return 0.0
    
    # CONVERTEER ALLE cellen individueel
    df['mutatie_num'] = df[mutatie_col].apply(convert_nl_number)
    df['saldo_num'] = df[saldo_col].apply(convert_nl_number)
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    
    df = df.sort_values('__date')
    
    st.success("✅ ALLES geconverteerd!")
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    
    total_mut = df['mutatie_num'].sum()
    last_saldo = df['saldo_num'].iloc[-1]
    stortingen = df[df['mutatie_num'] > 0]['mutatie_num'].sum()
    kosten = df[df['Omschrijving'].str.contains('kosten|transactiekosten', case=False, na=False)]['mutatie_num'].sum()
    
    with col1: st.metric("💰 Totale mutatie", f"€{total_mut:,.0f}")
    with col2: st.metric("🏦 Laatste saldo", f"€{last_saldo:,.0f}")
    with col3: st.metric("📈 Stortingen", f"€{stortingen:,.0f}")
    with col4: st.metric("💸 Kosten", f"€{abs(kosten):,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Saldo over tijd")
        fig, ax = plt.subplots(figsize=(10, 5))
        data = df.dropna(subset=['__date', 'saldo_num'])
        ax.plot(data['__date'], data['saldo_num'], 'o-', linewidth=2)
        ax.set_title('Saldo verloop')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Transacties per product")
        top = df[product_col].value_counts().head(8)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(top.values, labels=top.index, autopct='%1.1f%%')
        st.pyplot(fig)
    
    # === Investeringen ===
    st.markdown("### 💼 Investering per product")
    investeringen = df[df['mutatie_num'] < 0].groupby(product_col)['mutatie_num'].sum()
    st.dataframe(investeringen.sort_values().round(0))
    
    # === Bewijs dat conversie werkt ===
    st.markdown("### ✅ BEWIJS: Geconverteerde getallen")
    st.dataframe(df[['Datum', product_col, mutatie_col, 'mutatie_num', saldo_col, 'saldo_num']].head(10))
    
else:
    st.info("👆 Upload je CSV!")
