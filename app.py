import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees CSV correct voor DEGIRO formaat
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    # DEBUG: toon eerste rijen en kolommen
    st.subheader("🔍 DEBUG: Eerste 5 rijen (zoals Pandas ze ziet)")
    st.dataframe(df.head())
    
    # EXACTE kolomnamen uit jouw CSV
    date_col = 'Datum'
    product_col = 'Product'
    mutatie_col = 'Mutatie'
    saldo_col = 'Saldo'
    
    # Check of kolommen bestaan
    st.write(f"**Kolommen gevonden:** {list(df.columns)}")
    
    # Datum parsen (dd-mm-yyyy)
    if date_col in df.columns:
        df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.sort_values('__date')
    
    # NL getallen converteren (1.000,00 → 1000.00)
    def nl_to_float(series):
        return (series.astype(str)
                .str.replace(r'\.', '', regex=True)  # duizendtallen
                .str.replace(',', '.', regex=False)  # decimaal
                .replace('nan', '0')                 # lege cellen
                .astype(float))
    
    # Alleen converteren als kolom bestaat EN niet leeg is
    if mutatie_col in df.columns:
        df['mutatie_num'] = nl_to_float(df[mutatie_col])
        st.success("✅ Mutatie geconverteerd")
    else:
        df['mutatie_num'] = 0
    
    if saldo_col in df.columns:
        df['saldo_num'] = nl_to_float(df[saldo_col])
        st.success("✅ Saldo geconverteerd")
    else:
        df['saldo_num'] = 0
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_mut = df['mutatie_num'].sum()
        st.metric("💰 Totale mutatie", f"€{total_mut:,.0f}")
    
    with col2:
        last_saldo = df['saldo_num'].dropna().iloc[-1] if not df['saldo_num'].dropna().empty else 0
        st.metric("🏦 Laatste saldo", f"€{last_saldo:,.0f}")
    
    with col3:
        stortingen = df[df['mutatie_num'] > 0]['mutatie_num'].sum()
        st.metric("📈 Stortingen", f"€{stortingen:,.0f}")
    
    with col4:
        # Kosten regels detecteren
        kosten_mask = df[mutatie_col].astype(str).str.contains('kosten|transactiekosten|fee', case=False, na=False)
        kosten = df.loc[kosten_mask, 'mutatie_num'].sum()
        st.metric("💸 Kosten", f"€{abs(kosten):,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Saldo over tijd")
        if '__date' in df.columns and 'saldo_num' in df.columns:
            saldo_data = df.dropna(subset=['__date', 'saldo_num'])
            if len(saldo_data) > 1:
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(saldo_data['__date'], saldo_data['saldo_num'], linewidth=2, marker='o')
                ax.set_title('Saldo verloop')
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Transacties per product")
        if product_col in df.columns:
            top_products = df[product_col].dropna().value_counts().head(8)
            if len(top_products) > 0:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.pie(top_products.values, labels=top_products.index, autopct='%1.1f%%')
                ax.set_title('Transacties per product')
                st.pyplot(fig)
    
    # === Portfolio POSITIES ===
    st.markdown("### 💼 Huidige posities (investering per product)")
    if product_col in df.columns and 'mutatie_num' in df.columns:
        investeringen = df[df['mutatie_num'] < 0].groupby(product_col)['mutatie_num'].sum().sort_values()
        if not investeringen.empty:
            st.dataframe(investeringen.round(2))
        else:
            st.info("Geen investeringen gevonden")
    
else:
    st.info("👆 Upload je DEGIRO CSV!")
