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
    st.error("❌ Voeg Finnhub API key toe in `.streamlit/secrets.toml`")
    st.stop()

@st.cache_data(ttl=60)
def get_finnhub_price(symbol):
    try:
        # Crypto: BINANCE prefix
        if any(x in symbol for x in ['BTC', 'ETH']):
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

# ----------------- COMPLETE TICKER MAPPING -----------------
MANUAL_TICKERS = {
    'BITCOIN': 'BTCUSDT',
    'ETHEREUM': 'ETHUSDT',
    'VANGUARD FTSE ALL-WORLD UCITS': 'VWCE.DE',
    'FUTURE OF DEFENCE UCITS': 'NATC.AS',
    'AEGON LTD': 'AGN.AS',
    'AEGON': 'AGN.AS'
}

# ----------------- KOSTPRIJS FIX (DEGIRO SPECIFIEK) -----------------
def parse_degiro_positions(df):
    positions = {}
    
    for i, row in df.iterrows():
        product = str(row[3]).strip()
        oms = str(row[5]).strip()
        
        # KOOP detectie
        koop_match = re.search(r'KOOP\s+(\d+(?:,\d+)?)', oms, re.IGNORECASE)
        if koop_match:
            qty = float(koop_match.group(1).replace(',', '.'))
            
            # 🔧 KOSTPRIJS: zoek in VOLGENDE 3 rijen naar negatieve EUR bedrag
            cost = 0
            for j in range(i+1, min(i+4, len(df))):
                mutatie_cell = str(df.iloc[j][7]).strip()
                
                # Verwijder punten als duizend-scheiding, komma als decimaal
                clean_amount = re.sub(r'[^\d,-]', '', mutatie_cell).replace(',', '.')
                
                try:
                    amount = float(clean_amount)
                    if amount < 0:  # Negatief = uitgave (koop)
                        cost = abs(amount)
                        break
                except:
                    continue
            
            # ✅ AGGREGEER POSITIES
            if product not in positions:
                positions[product] = {'qty': 0, 'cost': 0, 'trades': []}
            positions[product]['qty'] += qty
            positions[product]['cost'] += cost
            positions[product]['trades'].append((qty, cost))
            
            st.success(f"✅ {product[:25]:<25} | {qty:>8.6f} | €{cost:>8,.0f}")
    
    return positions

# ----------------- MAIN -----------------
uploaded_file = st.file_uploader("📁 Upload Account.csv", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
    
    # Parse posities
    positions = parse_degiro_positions(df)
    st.success(f"📈 **{len(positions)} posities gevonden!**")
    
    if not positions:
        st.stop()
    
    # ----------------- LIVE KOEKSEN -----------------
    st.sidebar.markdown("### 📡 **Live Koersen**")
    live_prices = {}
    
    progress_bar = st.sidebar.progress(0)
    for i, product in enumerate(positions.keys()):
        ticker = find_ticker(product)
        st.sidebar.markdown(f"**{product[:25]}**")
        
        if ticker:
            price = get_finnhub_price(ticker)
            live_prices[product] = price
            
            status = "✅" if price else "❌"
            price_display = f"€{price:,.2f}" if price else "Geen data"
            st.sidebar.markdown(f"{status} `{ticker}`: **{price_display}**")
        else:
            st.sidebar.warning("❌ Geen ticker")
        st.sidebar.divider()
        
        progress_bar.progress((i+1) / len(positions))
    
    # ----------------- ULTIMATE DASHBOARD -----------------
    position_data = []
    total_cost = 0
    total_market = 0
    
    for product, data in positions.items():
        qty = data['qty']
        cost = data['cost']
        total_cost += cost
        
        price = live_prices.get(product)
        if price and cost > 0:
            market_value = qty * price
            rendement = ((market_value - cost) / cost * 100)
        else:
            market_value = 0
            rendement = 0
        total_market += market_value
        
        position_data.append({
            'Product': product[:30],
            '#': f"{qty:.6f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Koers': f"€{price:,.2f}" if price else 'N.v.t.',
            'Waarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%" if cost > 0 else '-'
        })
    
    # 🌟 SHINY KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Totaal Belegd", f"€{total_cost:,.0f}")
    col2.metric("📈 Huidige Waarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    col4.metric("💵 Winst/Verlies", f"€{total_market-total_cost:+,.0f}")
    
    # 📊
    col_left, col_right = st.columns([2,1])
    
    with col_left:
        st.markdown("### 💼 **Portfolio**")
        st.dataframe(pd.DataFrame(position_data), use_container_width=True)
    
    with col_right:
        st.markdown("### 📊 **Stats**")
        st.metric("Winning posities", sum(1 for p in position_data if 'Rendement' in p and float(p['Rendement'][:-1]) > 0))
        st.metric("Gem. rendement", f"{rendement_total:.1f}%")

else:
    st.info("👆 Upload je **Account.csv** van DEGIRO")
