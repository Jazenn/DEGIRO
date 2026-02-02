import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
import requests
import io

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")
st.title("🔥 DEGIRO Portfolio - LIVE RENDMENT")

# ----------------- FINNHUB API -----------------
try:
    FINNHUB_API_KEY = st.secrets["finnhub"]
except:
    st.error("❌ Voeg Finnhub API key toe in secrets.toml")
    st.stop()

@st.cache_data(ttl=120)
def get_finnhub_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()
        return float(data['c']) if 'c' in data and data['c'] else None
    except:
        return None

MANUAL_TICKERS = {
    'BITCOIN': 'BTCUSDT', 
    'ETHEREUM': 'ETHUSDT',
    'VANGUARD': 'VWCE.DE',
    'FUTURE OF DEFENCE': 'NATC.AS'
}

# ----------------- POSITIE PARSING (DEGIRO SPECIFIEK) -----------------
def parse_degiro_positions(df):
    """Parse DEGIRO kooptransacties uit omschrijving"""
    positions = {}
    
    for idx, row in df.iterrows():
        product = str(row[3])  # Product kolom
        oms = str(row[5]).upper()  # Omschrijving kolom
        
        # ✅ KOOP PATTERN: "KOOP 0,000077 @ 69.229,87 EUR"
        koop_match = re.search(r'KOOP\s+(\d+(?:,\d+)?)\s*@\s*[\d\.,]+\s*(?:EUR)', oms)
        
        if koop_match:
            quantity = float(koop_match.group(1).replace(',', '.'))
            
            # Bereken kostprijs uit volgende regel (Mutatie kolom 7)
            try:
                next_row = df.iloc[idx + 1]
                cost_str = str(next_row[7]).strip().replace('.', '').replace(',', '.')
                cost = abs(float(cost_str)) if cost_str.replace(',', '').replace('.', '').isdigit() else 0
            except:
                cost = 0  # Fallback
            
            st.success(f"✅ KOOP: {product} | {quantity} | €{cost:.2f}")
            
            if product not in positions:
                positions[product] = {'qty': 0, 'cost': 0}
            positions[product]['qty'] += quantity
            positions[product]['cost'] += cost
    
    return positions

# ----------------- MAIN -----------------
uploaded_file = st.file_uploader("📁 Upload DEGIRO CSV", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
    st.success(f"✅ CSV geladen: {df.shape}")
    
    # DEBUG: toon alleen KOOP transacties
    st.markdown("### 🔍 **KOOP TRANSACTIES GEVONDEN**")
    positions = parse_degiro_positions(df)
    
    st.success(f"📈 **{len(positions)} posities geparsed!**")
    
    if not positions:
        st.error("❌ Geen KOOP transacties. Check of 'KOOP' in omschrijvingen staat.")
        st.stop()
    
    # ----------------- LIVE PRINSEN -----------------
    st.sidebar.markdown("### 📡 **Live Koersen**")
    live_prices = {}
    
    for product in positions.keys():
        ticker = MANUAL_TICKERS.get(product.upper(), None)
        st.sidebar.write(f"**{product[:20]}**")
        
        if ticker:
            with st.sidebar.spinner(f"Fetch {ticker}..."):
                price = get_finnhub_price(ticker)
                live_prices[product] = price
                
                if price:
                    st.sidebar.success(f"✅ {ticker}: €{price:.4f}")
                else:
                    st.sidebar.error(f"❌ {ticker}: Geen data")
        else:
            st.sidebar.warning("❌ Geen ticker mapping")
            
        st.sidebar.divider()
    
    # ----------------- DASHBOARD -----------------
    position_data = []
    total_cost = sum(p['cost'] for p in positions.values())
    total_market = 0
    
    for product, data in positions.items():
        qty = data['qty']
        cost = data['cost']
        price = live_prices.get(product)
        
        if price:
            market_value = qty * price
            rendement = ((market_value - cost) / cost * 100)
        else:
            market_value = cost  
            rendement = 0
            
        total_market += market_value
        
        position_data.append({
            'Product': product,
            'Aantal': f"{qty:.6f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live Koers': f"€{price:.4f}" if price else 'N.v.t.',
            'Waarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%"
        })
    
    # KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Totaal Investering", f"€{total_cost:,.0f}")
    col2.metric("📈 Marktwaarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    col4.metric("🚀 Winst/Verlies", f"€{total_market-total_cost:+,.0f}")
    
    st.markdown("### 💼 **Portfolio Overzicht**")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

else:
    st.markdown("""
    ### 🚀 **Setup:**
    1. Finnhub API key in `.streamlit/secrets.toml`:
    ```toml
    finnhub = "cb123..."
    ```
    2. `pip install streamlit pandas requests matplotlib`
    """)
