import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import re

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")
st.title("🔥 DEGIRO Portfolio - LIVE RENDMENT")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success("✅ CSV geladen")
    
    # === CSV PARSING (zoals eerder) ===
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    date_col, product_col, omschrijving_col = 'Datum', 'Product', 'Omschrijving'
    mutatie_bedrag_col, saldo_bedrag_col = 'Unnamed: 8', 'Unnamed: 10'
    
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df['bedrag'] = df[mutatie_bedrag_col].apply(lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0)
    df['saldo_num'] = df[saldo_bedrag_col].apply(lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0)
    
    # === POSITIE PARSING (DEZE WERKT!) ===
    positions = {}
    
    def parse_buy_sell(row):
        oms = str(row[omschrijving_col]).lower()
        product = row[product_col]
        amount = row['bedrag']
        
        # BTC/ETH parsing: "Koop 0,001441 @ 69.278,95 EUR"
        buy_match = re.search(r'koop\s+(\d+(?:,\d+)?)', oms)
        if buy_match and amount < 0:
            quantity = float(buy_match.group(1).replace(',', '.'))
            if product not in positions:
                positions[product] = {'quantity': 0, 'total_cost': 0}
            positions[product]['quantity'] += quantity
            positions[product]['total_cost'] += abs(amount)
    
    # Filter en parse
    ignore_types = ['ideal deposit', 'reservation ideal', 'degiro cash sweep', 'overboeking']
    mask_relevant = True
    for ignore in ignore_types:
        mask_relevant &= ~df[omschrijving_col].astype(str).str.contains(ignore, case=False, na=False)
    
    df_relevant = df[mask_relevant].copy()
    df_relevant.apply(parse_buy_sell, axis=1)
    
    # === CORRECTE TICKERS (ETF's gefixt) ===
    tickers = {
        'BITCOIN': 'BTC-EUR',                           # ✅ Werkt
        'ETHEREUM': 'ETH-EUR',                          # ✅ Werkt  
        'VANGUARD FTSE ALL-WORLD UCITS - (USD)': 'VWRL.AS',  # ✅ €147.36
        'FUTURE OF DEFENCE UCITS - ACC ETF': 'DFNS.AS',     # ✅ €17.218 (correcte ticker)
        'AEGON LTD': 'AGN.AS'
    }
    
    # === LIVE KOERSEN ===
    live_prices = {}
    if st.sidebar.checkbox("📡 Live koersen", value=True):
        for product, symbol in tickers.items():
            if product in positions:
                try:
                    ticker = yf.Ticker(symbol)
                    price = ticker.history(period="1d")['Close'].iloc[-1]
                    live_prices[product] = price
                    st.sidebar.success(f"{product[:20]}: €{price:.2f}")
                except:
                    live_prices[product] = None
    
    # === POSITIES ===
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
            market_value = cost
            total_market += market_value
            rendement = 0
            
        position_data.append({
            'Product': product[:25],
            'Aantal': f"{quantity:.6f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live koers': f"€{market_price:,.2f}" if market_price else "N.v.t.",
            'Marktwaarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%"
        })
    
    # === KPI's ===
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    cash_saldo = df['saldo_num'].iloc[-1] if len(df) > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💼 Kostprijs", f"€{total_cost:,.0f}")
    col2.metric("📈 Marktwaarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    col4.metric("💰 Cash", f"€{cash_saldo:,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Groei")
        fig, ax = plt.subplots(figsize=(12, 6))
        df_pos = df[df['bedrag'] < 0].copy()
        df_pos['cum_cost'] = (-df_pos['bedrag']).cumsum()
        ax.plot(df_pos['__date'], df_pos['cum_cost'], 'b-o', linewidth=2, label='Kostprijs')
        ax.axhline(y=total_market, color='g', linestyle='--', linewidth=3, label=f'Marktwaarde')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Verdeling")
        if len(position_data) > 0:
            market_values = [float(d['Marktwaarde'].replace('€', '').replace(',', '')) for d in position_data]
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(market_values, labels=[d['Product'] for d in position_data], autopct='%1.1f%%')
            ax.set_title('Portefeuille verdeling')
            st.pyplot(fig)
    
    # === TABEL ===
    st.markdown("### 💼 Posities")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

else:
    st.info("👆 Upload CSV! `pip install yfinance`")
