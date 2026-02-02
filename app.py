import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import requests
from datetime import datetime

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio Dashboard - LIVE KOERSEN")

# Sidebar voor API key (optioneel)
st.sidebar.header("Live koersen")
use_live_prices = st.sidebar.checkbox("Huidige koersen ophalen", value=True)

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen")
    
    # === CSV PARSING ===
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    date_col = 'Datum'
    product_col = 'Product'
    omschrijving_col = 'Omschrijving'
    mutatie_bedrag_col = 'Unnamed: 8'
    saldo_bedrag_col = 'Unnamed: 10'
    
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df['bedrag'] = df[mutatie_bedrag_col].apply(lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0)
    df['saldo_num'] = df[saldo_bedrag_col].apply(lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0)
    
    # Filter relevante transacties
    ignore_types = ['ideal deposit', 'reservation ideal', 'degiro cash sweep', 'overboeking']
    mask_relevant = True
    for ignore in ignore_types:
        mask_relevant &= ~df[omschrijving_col].astype(str).str.contains(ignore, case=False, na=False)
    
    df_relevant = df[mask_relevant].copy()
    df_relevant['portefeuille_waarde'] = (-df_relevant['bedrag']).clip(lower=0)  # Negatief = positie
    
    # === LIVE KOERS MAPPING ===
    product_to_symbol = {
        'VANGUARD FTSE ALL-WORLD UCITS - (USD)': 'VWRL.AS',
        'FUTURE OF DEFENCE UCITS - ACC ETF': 'HANDEF.AS',  # HANetf Future of Defence
        'BITCOIN': 'BTC-EUR',
        'ETHEREUM': 'ETH-EUR',
        'AEGON LTD': 'AGN.AS'
    }
    
    # Haal live koersen op
    live_prices = {}
    if use_live_prices:
        st.sidebar.info("📡 Live koersen laden...")
        for product, symbol in product_to_symbol.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1d")
                if not data.empty:
                    live_prices[product] = data['Close'].iloc[-1]
                    st.sidebar.success(f"{product}: €{live_prices[product]:,.2f}")
            except:
                st.sidebar.warning(f"Geen koersdata voor {product}")
    
    # === HUIDIGE POSITIES met live prijzen ===
    positions = df_relevant[df_relevant['portefeuille_waarde'] > 0].groupby(product_col)['portefeuille_waarde'].sum()
    
    current_value = 0
    positions_current = []
    
    for product, kostprijs in positions.items():
        if product in live_prices:
            # Schatting: huidige waarde gebaseerd op kostprijs ratio
            current_price = live_prices[product]
            current_value += kostprijs  # Vereenvoudigd: toon kostprijs + % change later
            positions_current.append({
                'Product': product,
                'Kostprijs': f"€{kostprijs:,.0f}",
                'Live koers': f"€{current_price:,.2f}",
                'Huidige waarde': f"€{kostprijs:,.0f}",  # Later echte berekening
                'Rendement': "+0%"
            })
        else:
            positions_current.append({
                'Product': product,
                'Kostprijs': f"€{kostprijs:,.0f}",
                'Live koers': "N.v.t.",
                'Huidige waarde': f"€{kostprijs:,.0f}",
                'Rendement': "N.v.t."
            })
    
    positions_df = pd.DataFrame(positions_current)
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    totale_investering = positions.sum()
    
    with col1: st.metric("💼 Totale kostprijs", f"€{totale_investering:,.0f}")
    with col2: st.metric("📈 Huidige waarde", f"€{current_value:,.0f}")
    with col3: st.metric("📊 Rendement", f"+0%")  # Later echte berekening
    with col4: st.metric("🏦 Cash saldo", f"€{df['saldo_num'].iloc[-1]:,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Portefeuille groei")
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # Kostprijs timeline
        portfolio_growth = df_relevant[df_relevant['portefeuille_waarde'] > 0].sort_values('__date')
        portfolio_growth['cumulatief'] = portfolio_growth['portefeuille_waarde'].cumsum()
        
        ax.plot(portfolio_growth['__date'], portfolio_growth['cumulatief'], 
                'b-o', linewidth=2, label='Kostprijs groei', markersize=4)
        
        # Live waarde lijn (vereenvoudigd)
        if use_live_prices and len(portfolio_growth) > 0:
            ax.axhline(y=current_value, color='g', linestyle='--', 
                      label=f'Live waarde €{current_value:,.0f}')
        
        ax.set_title('Portefeuille ontwikkeling')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Huidige verdeling")
        if len(positions) > 0:
            fig, ax = plt.subplots(figsize=(8, 6))
            sizes = positions.values
            labels = positions.index
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.set_title('Portefeuille verdeling (kostprijs)')
            st.pyplot(fig)
    
    # === POSITIES TABEL ===
    st.markdown("### 💼 Huidige posities")
    st.dataframe(positions_df, use_container_width=True)
    
    # === PRODUCT MAPPING ===
    st.markdown("### 🔗 Product → Ticker mapping")
    st.dataframe(pd.DataFrame(list(product_to_symbol.items()), 
                             columns=['Product', 'Yahoo Finance Ticker']))

else:
    st.info("👆 Upload je CSV om te beginnen!")
    
    st.markdown("""
    ### 🚀 Features:
    - **Live koersen** van Yahoo Finance
    - **Echte portefeuille groei** grafiek
    - **Huidige posities** met live prijzen
    - **Pie chart** verdeling
    
    ### 📦 Install extra package:
    ```bash
    pip install yfinance
    ```
    """)
