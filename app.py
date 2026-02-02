import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
import requests
import time
import json

# ----------------- STREAMLIT SETTINGS -----------------
st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")
st.title("🔥 DEGIRO Portfolio - LIVE RENDMENT")

# ----------------- FINNHUB API -----------------
try:
    FINNHUB_API_KEY = st.secrets["finnhub"]
    if not FINNHUB_API_KEY or FINNHUB_API_KEY == "":
        st.error("❌ Finnhub API key niet gevonden in secrets!")
        st.stop()
except:
    st.error("❌ Voeg je Finnhub API key toe in Streamlit Secrets (finnhub)")
    st.stop()

@st.cache_data(ttl=120)  # Cache 2 minuten
def get_finnhub_price(symbol):
    """Haal de huidige prijs op via Finnhub met betere error handling"""
    try:
        st.info(f"🔍 Zoek koers voor: {symbol}")
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            st.warning(f"HTTP {response.status_code} voor {symbol}")
            return None
            
        data = response.json()
        st.info(f"Finnhub response voor {symbol}: {data}")
        
        # Controleer verschillende velden
        if 'c' in data and data['c'] is not None and data['c'] > 0:
            return float(data['c'])
        elif 'pc' in data and data['pc'] is not None and data['pc'] > 0:
            return float(data['pc'])
        else:
            st.warning(f"Geen geldige prijs in response voor {symbol}")
            return None
            
    except Exception as e:
        st.error(f"Finnhub error voor {symbol}: {str(e)}")
        return None

@st.cache_data(ttl=300)
def get_finnhub_symbol_search(query):
    """Zoek symbols via Finnhub"""
    try:
        url = f"https://finnhub.io/api/v1/search?q={query}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                return data['result'][:5]  # Top 5 resultaten
        return []
    except:
        return []

# ----------------- BETERE TICKER MAPPING -----------------
MANUAL_TICKERS = {
    'BITCOIN': 'BTCUSDT',  # Gebruik spot pairs i.p.v. futures
    'ETHEREUM': 'ETHUSDT',
    'VANGUARD FTSE ALL-WORLD UCITS ETF (USD)': 'VWCE.DE',  # Xetra ticker
    'FUTURE OF DEFENCE UCITS ETF': 'NATC.AS',  # Amsterdam ticker
    'VANECK SEMICONDUCTOR ETF': 'SMH',
    'ISHARES S&P 500 ETF': 'SPY',
    'AMUNDI NASDAQ 100 ETF': 'ANX.AS'
}

def find_best_ticker(product_name, isin=None):
    """Verbeterde ticker detectie"""
    upper_name = product_name.upper()
    
    # 1. Manual mapping
    for key in MANUAL_TICKERS:
        if key in upper_name:
            return MANUAL_TICKERS[key]
    
    # 2. ISIN naar ticker (vereenvoudigd)
    if isin:
        # Probeer bekende ISIN mappings
        isin_map = {
            'IE00B4L5Y983': 'VWCE.DE',
            'IE00BF0M2Z83': 'NATC.AS'
        }
        if isin in isin_map:
            return isin_map[isin]
    
    # 3. Finnhub search
    symbols = get_finnhub_symbol_search(product_name)
    if symbols:
        # Kies eerste geldige exchange
        for sym in symbols:
            if sym.get('exchange') in ['XETR', 'AMS', 'NASDAQ', 'NYSE']:
                return sym['symbol']
    
    # 4. Fallback: verwijder ETF/UCITS etc en probeer
    clean_name = re.sub(r'\(USD\)|\(EUR\)|UCITS|ETF', '', upper_name).strip()
    symbols = get_finnhub_symbol_search(clean_name)
    if symbols:
        return symbols[0]['symbol']
    
    return None

# ----------------- CSV UPLOAD -----------------
uploaded_file = st.file_uploader("📁 Upload je DEGIRO CSV", type=['csv', 'txt'])

if uploaded_file is not None:
    st.success("✅ CSV geladen!")
    
    # Reset file pointer
    uploaded_file.seek(0)
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')  # DEGIRO gebruikt vaak ;
    except:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=',', encoding='latin1')
    
    st.info(f"📊 CSV vorm: {df.shape}")
    
    # Auto-detect kolommen
    date_col = next((col for col in df.columns if 'datum' in col.lower()), 'Datum')
    product_col = next((col for col in df.columns if 'product' in col.lower()), 'Product')
    omschrijving_col = next((col for col in df.columns if 'omschrijving' in col.lower()), 'Omschrijving')
    
    st.info(f"🔍 Gebruikt kolommen: Datum={date_col}, Product={product_col}")
    
    # Data conversie
    df['__date'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df['bedrag'] = pd.to_numeric(df.iloc[:, -2].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
    df['saldo_num'] = pd.to_numeric(df.iloc[:, -1].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
    
    # ----------------- POSITIES PARSING -----------------
    def parse_positions(df):
        positions = {}
        for _, row in df.iterrows():
            oms = str(row[omschrijving_col]).lower()
            
            # Koop detectie (bedrag < 0)
            if row['bedrag'] < 0 and ('koop' in oms or 'buy' in oms):
                quantity_match = re.search(r'(@|x|@\s)(\d+(?:,\d+)?)', oms)
                if quantity_match:
                    quantity = float(quantity_match.group(2).replace(',', '.'))
                    product = row[product_col]
                    
                    if product not in positions:
                        positions[product] = {'quantity': 0, 'total_cost': 0}
                    positions[product]['quantity'] += quantity
                    positions[product]['total_cost'] += abs(row['bedrag'])
        return positions
    
    positions = parse_positions(df)
    st.success(f"📈 {len(positions)} posities gevonden!")
    
    # ----------------- LIVE PRINSEN -----------------
    st.sidebar.markdown("### 📡 Live Koersen")
    
    tickers = {}
    live_prices = {}
    
    for product in list(positions.keys()):
        with st.sidebar:
            with st.spinner(f"Zoek ticker voor {product[:30]}..."):
                ticker = find_best_ticker(product)
                tickers[product] = ticker
                st.write(f"**{product[:25]}** → {ticker}")
                
                if ticker:
                    price = get_finnhub_price(ticker)
                    live_prices[product] = price
                    if price:
                        st.success(f"✅ €{price:.2f}")
                    else:
                        st.error("❌ Geen koers")
                else:
                    st.error("❌ Geen ticker")
                st.divider()
    
    # ----------------- DASHBOARD -----------------
    position_data = []
    total_cost = sum(p['total_cost'] for p in positions.values())
    total_market = 0
    
    for product, data in positions.items():
        quantity = data['quantity']
        cost = data['total_cost']
        price = live_prices.get(product)
        
        if price:
            market_value = quantity * price
            rendement = ((market_value - cost) / cost * 100)
        else:
            market_value = cost
            rendement = 0
            
        total_market += market_value
        
        position_data.append({
            'Product': product[:30],
            'Aantal': f"{quantity:.4f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live': f"€{price:.2f}" if price else "N.v.t.",
            'Waarde': f"€{market_value:,.0f}",
            'Rendement': f"{rendement:+.1f}%"
        })
    
    # KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    cash = df['saldo_num'].iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💼 Kostprijs", f"€{total_cost:,.0f}")
    col2.metric("📈 Marktwaarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    col4.metric("💰 Cash", f"€{cash:,.0f}")
    
    # Charts + Tabel
    st.markdown("### 💼 Posities")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)
    
else:
    st.info("👆 Upload je DEGIRO CSV export (Export > Portfolio > CSV)")
    st.markdown("""
    ### 🔧 Setup:
    1. Ga naar [finnhub.io](https://finnhub.io), maak gratis account
    2. Voeg API key toe: `.streamlit/secrets.toml`
    ```
    finnhub = "jouw_api_key_hier"
    ```
    3. Installeer: `pip install streamlit pandas matplotlib requests`
    """)
