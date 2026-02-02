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
    st.error("❌ Voeg Finnhub API key toe")
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
    'BITCOIN': 'BTCUSDT', 'ETHEREUM': 'ETHUSDT', 'VANGUARD': 'VWCE.DE', 
    'FUTURE OF DEFENCE': 'NATC.AS', 'S&P 500': 'SPY', 'NASDAQ': 'QQQ'
}

def find_ticker(product):
    upper = product.upper()
    for key, ticker in MANUAL_TICKERS.items():
        if key in upper:
            return ticker
    return None

# ----------------- CSV UPLOAD -----------------
uploaded_file = st.file_uploader("📁 Upload DEGIRO CSV", type=['csv'])

if uploaded_file is not None:
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
    
    st.success(f"✅ CSV geladen: {df.shape}")
    
    # Kolommen volgens jouw output
    date_col, product_col, oms_col, mutatie_col, saldo_col = 0, 3, 5, 7, 9
    
    st.markdown("### 🔍 **INSPECTIE: Eerste 10 transacties**")
    display_df = df.iloc[:, [date_col, product_col, oms_col, mutatie_col]].copy()
    display_df.columns = ['Datum', 'Product', 'Omschrijving', 'Mutatie']
    st.dataframe(display_df.head(10), height=400)
    
    # ----------------- VERBETERDE POSITIE DETECTIE -----------------
    st.markdown("### 🔍 **ANALYSE OMSCHRIJVINGEN**")
    
    positions = {}
    koops = []
    
    for idx, row in df.iterrows():
        datum = row[date_col]
        product = str(row[product_col])
        oms = str(row[oms_col]).upper()
        mutatie_str = str(row[mutatie_col])
        
        # Nederlandse/Europese getal conversie
        mutatie_clean = re.sub(r'[^\d,-]', '', mutatie_str).replace(',', '.')
        try:
            mutatie = float(mutatie_clean)
        except:
            continue
            
        st.write(f"**{datum}** | {product[:30]} | €{mutatie:,.0f}")
        st.write(f"  → OMS: `{oms[:80]}`")
        
        # MEERDE KOOP PATTERNS
        koop_patterns = [
            r'KOOP', r'BUY', r'PURCHASE',
            r'@', r'X\s+\d', r'\d+\s+X',  # Quantity indicators
        ]
        
        is_koop = mutatie < 0 and any(re.search(pattern, oms) for pattern in koop_patterns)
        
        if is_koop:
            st.error(f"✅ KOOP GEVONDEN: {product}")
            koops.append((product, mutatie))
            
            # Quantity uit omschrijving halen
            qty_match = re.search(r'(\d+(?:,\d{1,2})?)', oms)
            qty = float(qty_match.group(1).replace(',', '.')) if qty_match else 1
            
            if product not in positions:
                positions[product] = {'qty': 0, 'cost': 0}
            positions[product]['qty'] += qty
            positions[product]['cost'] += abs(mutatie)
    
    st.success(f"📈 **{len(koops)} kooptransacties** → **{len(positions)} posities**")
    
    if not positions:
        st.warning("❌ Geen matches. Pas de patterns aan op basis van je omschrijvingen hierboven!")
        st.stop()
    
    # ----------------- LIVE KOEKSEN -----------------
    st.sidebar.markdown("### 📡 Live Koersen")
    live_prices = {}
    
    for product in positions:
        ticker = find_ticker(product)
        st.sidebar.write(f"{product[:25]}")
        if ticker:
            price = get_finnhub_price(ticker)
            live_prices[product] = price
            color, icon = "normal", "➡️"
            if price: color, icon = "success", "✅"
            else: color, icon = "error", "❌"
            st.sidebar.markdown(f"**{ticker}**: {'€' + f'{price:.2f}' if price else 'N.v.t.'}", 
                              unsafe_allow_html=True)
        st.sidebar.divider()
    
    # ----------------- DASHBOARD -----------------
    total_cost = sum(p['cost'] for p in positions.values())
    total_market = 0
    
    position_data = []
    for product, data in positions.items():
        qty, cost = data['qty'], data['cost']
        price = live_prices.get(product)
        market = qty * price if price else cost
        rendement = ((market - cost) / cost * 100) if cost > 0 else 0
        
        total_market += market
        
        position_data.append({
            'Product': product[:25],
            'Aantal': f"{qty:.2f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live': f"€{price:.2f}" if price else 'N.v.t.',
            'Waarde': f"€{market:,.0f}",
            'Rendement': f"{rendement:+.1f}%"
        })
    
    # KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💼 Investering", f"€{total_cost:,.0f}")
    col2.metric("📈 Waarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    
    st.markdown("### 💼 Posities")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

else:
    st.info("👆 Upload je Account.csv")
