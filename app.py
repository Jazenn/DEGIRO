import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import re
from datetime import datetime

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Portfolio - LIVE RENDMENT")

# Live koersen checkbox
use_live = st.sidebar.checkbox("📡 Live koersen", value=True)

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success("✅ CSV geladen")
    
    # === CSV PARSING ===
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    date_col, product_col, omschrijving_col = 'Datum', 'Product', 'Omschrijving'
    mutatie_bedrag_col, saldo_bedrag_col = 'Unnamed: 8', 'Unnamed: 10'
    
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df['bedrag'] = df[mutatie_bedrag_col].apply(lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0)
    
    # === POSITIE PARSING ===
    positions = {}  # {product: {'quantity': 0, 'total_cost': 0}}
    
    def parse_buy_sell(row):
        oms = str(row[omschrijving_col]).lower()
        product = row[product_col]
        amount = row['bedrag']
        
        # Koop parsing: "Koop 0,001441 @ 69.278,95 EUR"
        buy_match = re.search(r'koop\s+(\d+(?:,\d+)?)\s*@', oms)
        if buy_match and amount < 0:  # Koop = negatief
            quantity = float(buy_match.group(1).replace(',', '.'))
            if product not in positions:
                positions[product] = {'quantity': 0, 'total_cost': 0}
            positions[product]['quantity'] += quantity
            positions[product]['total_cost'] += abs(amount)
    
    # Filter relevante + parse posities
    ignore_types = ['ideal deposit', 'reservation ideal', 'degiro cash sweep', 'overboeking']
    mask_relevant = True
    for ignore in ignore_types:
        mask_relevant &= ~df[omschrijving_col].astype(str).str.contains(ignore, case=False, na=False)
    
    df_relevant = df[mask_relevant].apply(parse_buy_sell, axis=1)
    
    # === LIVE KOERSEN ===
    tickers = {
        'BITCOIN': 'BTC-EUR',
        'ETHEREUM': 'ETH-EUR', 
        'VANGUARD FTSE ALL-WORLD UCITS - (USD)': 'VWRL.AS',
        'FUTURE OF DEFENCE UCITS - ACC ETF': 'NVDX.AS',  # HANetf Defence
        'AEGON LTD': 'AGN.AS'
    }
    
    live_prices = {}
    if use_live:
        with st.spinner("📡 Live koersen ophalen..."):
            for product, symbol in tickers.items():
                if product in positions:
                    try:
                        ticker = yf.Ticker(symbol)
                        price = ticker.history(period="1d")['Close'].iloc[-1]
                        live_prices[product] = price
                    except:
                        live_prices[product] = None
    
    # === POSITIES TABEL ===
    position_data = []
    total_cost = 0
    total_market = 0
    
    for product, data in positions.items():
        quantity = data['quantity']
        cost = data['total_cost']
        total_cost += cost
        
        market_price = live_prices.get(product)
        if market_price:
            market_value = quantity * market_price
            total_market += market_value
            rendement = ((market_value - cost) / cost * 100)
        else:
            market_value = cost  # Fallback
            rendement = 0
            
        position_data.append({
            'Product': product,
            'Aantal': f"{quantity:.6f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live koers': f"€{market_price:,.2f}" if market_price else "N.v.t.",
            'Marktwaarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%"
        })
    
    positions_df = pd.DataFrame(position_data)
    
    # === KPI's ===
    col1, col2, col3, col4 = st.columns(4)
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    with col1: st.metric("💼 Totale kostprijs", f"€{total_cost:,.0f}")
    with col2: st.metric("📈 Marktwaarde", f"€{total_market:,.0f}")
    with col3: st.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    with col4: st.metric("💰 Cash", f"€{df['saldo_num'].iloc[-1]:,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Portefeuille groei")
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Kostprijs timeline
        df_pos = df[df['bedrag'] < 0].copy()
        df_pos['cum_cost'] = (-df_pos['bedrag']).cumsum()
        ax.plot(df_pos['__date'], df_pos['cum_cost'], 'b-o', linewidth=2, label='Kostprijs', markersize=4)
        
        # Live waarde lijn
        ax.axhline(y=total_market, color='g', linestyle='--', linewidth=3, 
                  label=f'Live marktwaarde €{total_market:,.0f}')
        
        ax.set_title('Kostprijs vs Live waarde')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Verdeling")
        if len(positions) > 0:
            market_values = [row['Marktwaarde'].replace('€', '').replace(',', '') for row in position_data]
            market_values = [float(v) for v in market_values]
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(market_values, labels=[row['Product'] for row in position_data], autopct='%1.1f%%')
            ax.set_title('Portefeuille verdeling')
            st.pyplot(fig)
    
    # === POSITIES ===
    st.markdown("### 💼 Gedetailleerde posities")
    st.dataframe(positions_df, use_container_width=True)
    
    # === TICKER INFO ===
    st.markdown("### 🔗 Gebruikte tickers")
    ticker_df = pd.DataFrame(list(tickers.items()), columns=['Product', 'Yahoo Ticker'])
    st.dataframe(ticker_df)

else:
    st.info("👆 Upload CSV!")
    st.info("💡 `pip install yfinance` vereist")
