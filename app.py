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
    try:
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

def find_ticker(product):  # ❌ ONTBREKENDE FUNCTIE GEFIXT
    upper = product.upper()
    MANUAL_TICKERS = {
        'BITCOIN': 'BTCUSDT',
        'ETHEREUM': 'ETHUSDT',
        'VANGUARD FTSE ALL-WORLD UCITS': 'VWCE.DE',
        'FUTURE OF DEFENCE UCITS': 'NATC.AS',
        'AEGON LTD': 'AGN.AS',
        'AEGON': 'AGN.AS'
    }
    for key, ticker in MANUAL_TICKERS.items():
        if key in upper:
            return ticker
    return None

# ----------------- KOSTPRIJS PARSING GEFIXT -----------------
def parse_degiro_positions(df):
    positions = {}
    
    for i, row in df.iterrows():
        product = str(row[3]).strip()
        oms = str(row[5]).strip()
        
        # ✅ REGEX FIX: geen escape chars nodig
        koop_match = re.search(r'KOOP\s+(\d+(?:,\d+)?)', oms, re.IGNORECASE)
        if koop_match:
            qty = float(koop_match.group(1).replace(',', '.'))
            
            # 🔧 KOSTPRIJS: zoek NEGATIEF bedrag in volgende rijen
            cost = 0
            for j in range(i+1, min(i+4, len(df))):
                mutatie_cell = str(df.iloc[j][7]).strip()
                
                # ✅ FIX: normale regex, Nederlandse notatie
                clean_amount = re.sub(r'[^\d,-]', '', mutatie_cell).replace(',', '.')
                
                try:
                    amount = float(clean_amount)
                    if amount < 0:  # Negatief = koop uitgave
                        cost = abs(amount)
                        break
                except:
                    continue
            
            if product not in positions:
                positions[product] = {'qty': 0, 'cost': 0}
            positions[product]['qty'] += qty
            positions[product]['cost'] += cost
            
            st.success(f"✅ {product[:25]:<25} | {qty:>8.6f} | €{cost:>7,.0f}")
    
    return positions

# ----------------- MAIN DASHBOARD -----------------
uploaded_file = st.file_uploader("📁 Upload Account.csv", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
    
    positions = parse_degiro_positions(df)
    st.success(f"📈 **{len(positions)} posities gevonden!**")
    
    if not positions:
        st.error("❌ Geen posities. Check omschrijvingen.")
        st.stop()
    
    # ----------------- LIVE KOEKSEN -----------------
    st.sidebar.markdown("### 📡 **Live Koersen**")
    live_prices = {}
    
    for product in positions.keys():
        ticker = find_ticker(product)
        st.sidebar.markdown(f"**{product[:25]}**")
        
        if ticker:
            price = get_finnhub_price(ticker)
            live_prices[product] = price
            
            if price:
                st.sidebar.success(f"✅ `{ticker}`: **€{price:,.2f}**")
            else:
                st.sidebar.error(f"❌ `{ticker}`: Geen data")
        else:
            st.sidebar.warning("❌ Geen bekende ticker")
        st.sidebar.divider()
    
    # ----------------- PORTFOLIO -----------------
    position_data = []
    total_cost = sum(p['cost'] for p in positions.values())
    total_market = 0
    
    for product, data in positions.items():
        qty = data['qty']
        cost = data['cost']
        
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
            'Aantal': f"{qty:.6f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live': f"€{price:,.2f}" if price else 'N.v.t.',
            'Waarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%" if cost > 0 else '-'
        })
    
    # 🌟 KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Totaal Belegd", f"€{total_cost:,.0f}")
    col2.metric("📈 Huidige Waarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    col4.metric("💵 Winst", f"€{total_market-total_cost:+,.0f}")
    
    st.markdown("### 💼 **Portfolio Overzicht**")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

else:
    st.info("👆 Upload je DEGIRO **Account.csv**")
