import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
import requests

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")
st.title("🔥 DEGIRO Portfolio - LIVE RENDMENT")

# ----------------- FINNHUB API -----------------
try:
    FINNHUB_API_KEY = st.secrets["finnhub"]
except:
    st.error("❌ Voeg Finnhub API key toe")
    st.stop()

@st.cache_data(ttl=60)
def get_finnhub_price(symbol):
    """Fix: BINANCE prefix voor crypto"""
    try:
        # Crypto: BINANCE:BTCUSDT formaat
        if 'BTC' in symbol or 'ETH' in symbol:
            full_symbol = f"BINANCE:{symbol}"
        else:
            full_symbol = symbol
            
        url = f"https://finnhub.io/api/v1/quote?symbol={full_symbol}&token={FINNHUB_API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        price = data.get('c') or data.get('pc')
        return float(price) if price else None
    except:
        return None

# ----------------- PERFECTE TICKER MAPPING -----------------
MANUAL_TICKERS = {
    'BITCOIN': 'BTCUSDT',
    'ETHEREUM': 'ETHUSDT',
    'VANGUARD FTSE ALL-WORLD UCITS': 'VWCE.DE',
    'FUTURE OF DEFENCE UCITS': 'NATC.AS', 
    'AEGON LTD': 'AGN.AS'
}

def find_ticker(product):
    upper = product.upper()
    for key, ticker in MANUAL_TICKERS.items():
        if key in upper:
            return ticker
    return None

# ----------------- DEGIRO PARSING (GEFIXT) -----------------
def parse_degiro_positions(df):
    positions = {}
    
    for i, row in df.iterrows():
        product = str(row[3])  # Kolom 3 = Product
        oms = str(row[5])      # Kolom 5 = Omschrijving
        
        # ✅ KOOP PATTERN
        koop_match = re.search(r'KOOP\s+(\d+(?:,\d+)?)', oms, re.IGNORECASE)
        if koop_match:
            qty = float(koop_match.group(1).replace(',', '.'))
            
            # ✅ KOSTPRIJS uit MUATIE kolom (2 regels later!)
            cost = 0
            for j in range(i+1, min(i+4, len(df))):
                next_row = df.iloc[j]
                cost_str = str(next_row[7]).strip()  # Kolom 7 = Mutatie
                if cost_str.replace('.', '').replace(',', '').replace('-', '').isdigit():
                    cost = abs(float(cost_str.replace('.', '').replace(',', '.')))
                    break
            
            if product not in positions:
                positions[product] = {'qty': 0, 'cost': 0}
            positions[product]['qty'] += qty
            positions[product]['cost'] += cost
            
            st.success(f"✅ {product[:20]}: {qty:>10} stuks | €{cost:>8,.0f}")
    
    return positions

# ----------------- MAIN DASHBOARD -----------------
uploaded_file = st.file_uploader("📁 Upload Account.csv", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
    
    positions = parse_degiro_positions(df)
    st.success(f"📈 **{len(positions)} posities geladen!**")
    
    if not positions:
        st.error("Geen KOOP transacties gevonden")
        st.stop()
    
    # ----------------- LIVE PRINSEN -----------------
    st.sidebar.markdown("### 📡 **Live Koersen**")
    live_prices = {}
    
    for product in positions.keys():
        ticker = find_ticker(product)
        st.sidebar.write(f"**{product[:25]}**")
        
        if ticker:
            price = get_finnhub_price(ticker)
            live_prices[product] = price
            
            if price:
                st.sidebar.success(f"✅ `{ticker}`: **€{price:,.2f}**")
            else:
                st.sidebar.error(f"❌ `{ticker}`: Geen data")
        else:
            st.sidebar.warning("❌ Geen ticker")
        st.sidebar.divider()
    
    # ----------------- OVERZICHT -----------------
    position_data = []
    total_cost = 0
    total_market = 0
    
    for product, data in positions.items():
        qty, cost = data['qty'], data['cost']
        total_cost += cost
        
        price = live_prices.get(product)
        if price:
            market_value = qty * price
            rendement = ((market_value - cost) / cost * 100) if cost > 0 else 0
        else:
            market_value = cost
            rendement = 0
        total_market += market_value
        
        position_data.append({
            'Product': product[:30],
            'Aantal': f"{qty:.6f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live': f"€{price:,.2f}" if price else 'N.v.t.',
            'Waarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%" 
        })
    
    # KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Totaal Investering", f"€{total_cost:,.0f}")
    col2.metric("📈 Marktwaarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    col4.metric("💵 Winst/Verlies", f"€{total_market-total_cost:+,.0f}")
    
    st.markdown("### 💼 **Portfolio**")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

else:
    st.info("👆 Upload je DEGIRO **Account.csv**")
