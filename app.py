import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees CSV met flexibele separator
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=None, engine="python")
    
    st.subheader("📊 Portfolio Inzichten")
    
    # Normaliseer kolomnamen
    cols_lower = {col.lower(): col for col in df.columns}
    print("Beschikbare kolommen:", list(cols_lower.keys()))  # Debug info
    
    date_col = cols_lower.get('datum', None)
    product_col = cols_lower.get('product', None)
    mutatie_col = cols_lower.get('mutatie', None)
    saldo_col = cols_lower.get('saldo', None)
    
    # Datum parsen
    if date_col:
        df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.sort_values('__date')
    
    # ROBUUSTE NL-naar-float conversie
    def nl_to_float_safe(series):
        def clean_value(x):
            if pd.isna(x):
                return None
            s = str(x).strip()
            if s == '' or s.lower() == 'nan':
                return None
            s = s.replace('.', '', 1)  # EERSTE punt (duizendtal) weg
            s = s.replace('.', '')     # Resterende punten (decimaal) behouden? Nee, allemaal weg
            s = s.replace(',', '.')
            try:
                return float(s)
            except:
                return None
        
        return pd.Series(series).apply(clean_value)
    
    # Veilige numerieke conversie
    if mutatie_col and mutatie_col in df.columns:
        df['mutatie_num'] = nl_to_float_safe(df[mutatie_col])
        st.success(f"✅ Mutatie kolom gevonden en geconverteerd: {mutatie_col}")
    else:
        st.warning("⚠️ Mutatie kolom niet gevonden")
        df['mutatie_num'] = 0
    
    if saldo_col and saldo_col in df.columns:
        df['saldo_num'] = nl_to_float_safe(df[saldo_col])
        st.success(f"✅ Saldo kolom gevonden en geconverteerd: {saldo_col}")
    else:
        st.warning("⚠️ Saldo kolom niet gevonden")
        df['saldo_num'] = 0
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_mut = df['mutatie_num'].sum()
        st.metric("💰 Totale mutatie", f"€{total_mut:,.0f}")
    
    with col2:
        last_saldo = df['saldo_num'].dropna().iloc[-1] if len(df['saldo_num'].dropna()) > 0 else 0
        st.metric("🏦 Laatste saldo", f"€{last_saldo:,.0f}")
    
    with col3:
        stortingen = df[df['mutatie_num'] > 0]['mutatie_num'].sum()
        st.metric("📈 Stortingen", f"€{stortingen:,.0f}")
    
    with col4:
        kosten_mask = df[mutatie_col].astype(str).str.contains('kosten|transactiekosten|fee', case=False, na=False)
        kosten = df.loc[kosten_mask, 'mutatie_num'].sum()
        st.metric("💸 Kosten", f"€{abs(kosten):,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Saldo over tijd")
        saldo_data = df.dropna(subset=['__date', 'saldo_num'])
        if not saldo_data.empty and len(saldo_data) > 1:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(saldo_data['__date'], saldo_data['saldo_num'], linewidth=2, marker='o', markersize=4)
            ax.set_title('Saldo verloop')
            ax.set_xlabel('Datum')
            ax.set_ylabel('Saldo (€)')
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            st.pyplot(fig)
        else:
            st.info("Niet genoeg saldo data voor grafiek")
    
    with colB:
        st.markdown("### 🥧 Transacties per product")
        if product_col and product_col in df.columns:
            top_products = df[product_col].dropna().value_counts().head(8)
            if not top_products.empty:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.pie(top_products.values, labels=top_products.index, autopct='%1.1f%%', textprops={'fontsize': 8})
                ax.set_title('Verdeling transacties per product')
                st.pyplot(fig)
            else:
                st.info("Geen product data gevonden")
    
    # === Posities ===
    st.markdown("### 📋 Transacties per product (investering)")
    if product_col and mutatie_col:
        investeringen = df[df['mutatie_num'] < 0].groupby(product_col)['mutatie_num'].sum().sort_values()
        if not investeringen.empty:
            st.dataframe(investeringen)
        else:
            st.info("Geen investeringstransacties gevonden")
    
    # === Raw data preview ===
    st.markdown("### 📄 Eerste 10 rijen")
    st.dataframe(df[['__date', product_col, mutatie_col, saldo_col, 'mutatie_num', 'saldo_num']].head(10) if all(c in df.columns for c in [product_col, mutatie_col, saldo_col]) else df.head(10))
    
else:
    st.info("👆 Upload je DEGIRO CSV bestand om te beginnen!")
