import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
import requests
import time
import json
import io

# ----------------- STREAMLIT SETTINGS -----------------
st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")
st.title("🔥 DEGIRO Portfolio - LIVE RENDMENT")

# ----------------- FINNHUB API -----------------
try:
    FINNHUB_API_KEY = st.secrets["finnhub"]
    if not FINNHUB_API_KEY or FINNHUB_API_KEY == "":
        st.error("❌ Finnhub API key niet gevonden!")
        st.stop()
except:
    st.error("❌ Voeg Finnhub API key toe in secrets.toml")
    st.stop()

# ----------------- BETERE CSV PARSING -----------------
def parse_degiro_csv(file_content):
    """Parse DEGIRO CSV met automatische kolom detectie"""
    # Probeer verschillende encodings en separators
    encodings = ['utf-8', 'latin1', 'iso-8859-1']
    separators = [';', ',', '\t']
    
    df = None
    for encoding in encodings:
        try:
            content = file_content.read().decode(encoding)
            for sep in separators:
                try:
                    df = pd.read_csv(io.StringIO(content), sep=sep)
                    if len(df.columns) > 5:  # Minimaal 5 kolommen = geldig
                        st.success(f"✅ Geparsed met {encoding}, separator '{sep}'")
                        return df
                except:
                    continue
        except:
            continue
    
    # ULTIEKE FALLBACK: handmatig splitten van 1-kolom CSV
    st.warning("🔧 Probeer handmatige kolom splitting...")
    lines = file_content.read().decode('latin1').split('\n')
    rows = []
    
    for line in lines[1:]:  # Skip header
        if not line.strip():
            continue
        # Split op veelvoorkomende DEGIRO patronen
        parts = re.split(r'[;\t,]', line, maxsplit=12)
        if len(parts) >= 8:
            rows.append([p.strip() for p in parts])
    
    if rows:
        df = pd.DataFrame(rows)
        st.success(f"✅ Handmatig geparsed: {len(rows)} rows")
        return df
    
    st.error("❌ Kan CSV niet parsen!")
    return None

@st.cache_data(ttl=120)
def get_finnhub_price(symbol):
    """Finnhub price fetch met debug"""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if response.status_code == 200 and 'c' in data and data['c']:
            return float(data['c'])
        return None
    except:
        return None

MANUAL_TICKERS = {
    'BITCOIN': 'BTCUSDT',
    'ETHEREUM': 'ETHUSDT', 
    'VANGUARD FTSE': 'VWCE.DE',
    'FUTURE OF DEFENCE': 'NATC.AS',
    'S&P 500': 'SPY',
    'NASDAQ': 'QQQ'
}

def find_ticker(product):
    """Eenvoudige ticker mapping"""
    upper = product.upper()
    for key, ticker in MANUAL_TICKERS.items():
        if key in upper:
            return ticker
    return None

# ----------------- UPLOAD & PARSE -----------------
uploaded_file = st.file_uploader("📁 Upload DEGIRO CSV", type=['csv', 'txt'])

if uploaded_file is not None:
    uploaded_file.seek(0)
    st.success("✅ CSV geladen")
    
    # BELANGRIJK: reset & parse
    uploaded_file.seek(0)
    df = parse_degiro_csv(uploaded_file)
    
    if df is None:
        st.error("❌ Parsing mislukt!")
        st.stop()
    
    # DEBUG: toon eerste rows en kolommen
    st.markdown("### 🔍 **DEBUG: Eerste 3 rows**")
    st.dataframe(df.head(3), use_container_width=True)
    
    st.markdown("### 🔍 **Kolommen gevonden**")
    st.write(f"`{list(df.columns)}` ({len(df.columns)} kolommen)")
    
    # Auto-detect kolommen (flexibeler)
    date_col = next((i for i, col in enumerate(df.columns) if 'datum' in str(col).lower()), 0)
    product_col = next((i for i, col in enumerate(df.columns) if 'product' in str(col).lower()), 3)
    oms_col = next((i for i, col in enumerate(df.columns) if 'omschrijving' in str(col).lower()), 5)
    amount_col = next((i for i, col in enumerate(df.columns) if 'mutatie' in str(col).lower()), -2)
    
    st.info(f"🔍 **Auto-detect**: Datum={date_col}, Product={product_col}, Oms={oms_col}, Bedrag={amount_col}")
    
    # ----------------- POSITIES EXTRAHEREN -----------------
    positions = {}
    
    for idx, row in df.iterrows():
        try:
            oms = str(row[oms_col]).lower() if pd.notna(row[oms_col]) else ""
            product = str(row[product_col]) if pd.notna(row[product_col]) else "Onbekend"
            amount_str = str(row[amount_col]) if pd.notna(row[amount_col]) else "0"
            
            # Nederlandse getal conversie
            amount = float(re.sub(r'[^\d,-]', '', amount_str).replace(',', '.'))
            
            # Koop detectie: negatief bedrag + koop/buy
            if amount < 0 and ('koop' in oms or 'buy' in oms):
                # Extract quantity uit omschrijving (bijv. "KOOP 10,5 @ 50.00")
                qty_match = re.search(r'(\d+(?:,\d+)?)\s*(x|@)', oms)
                if qty_match:
                    qty = float(qty_match.group(1).replace(',', '.'))
                    
                    if product not in positions:
                        positions[product] = {'qty': 0, 'cost': 0}
                    positions[product]['qty'] += qty
                    positions[product]['cost'] += abs(amount)
                    
        except:
            continue
    
    st.success(f"📈 **{len(positions)} posities gevonden!**")
    
    if not positions:
        st.warning("⚠️ Geen kooptransacties gevonden. Check de omschrijvingen hierboven.")
        st.stop()
    
    # ----------------- LIVE KOEKSEN -----------------
    st.sidebar.markdown("### 📡 **Live Koersen**")
    
    live_prices = {}
    for product, data in positions.items():
        ticker = find_ticker(product)
        st.sidebar.write(f"**{product[:25]}**")
        
        if ticker:
            price = get_finnhub_price(ticker)
            live_prices[product] = price
            if price:
                st.sidebar.success(f"✅ {ticker}: €{price:.2f}")
            else:
                st.sidebar.error(f"❌ {ticker}: Geen data")
        else:
            st.sidebar.warning("❌ Geen bekende ticker")
            live_prices[product] = None
        
        st.sidebar.divider()
    
    # ----------------- DASHBOARD -----------------
    position_data = []
    total_cost = sum(p['cost'] for p in positions.values())
    total_market = 0
    
    for product, data in positions.items():
        qty = data['qty']
        cost = data['cost']
        price = live_prices.get(product)
        
        market_val = qty * price if price else cost
        rendement = ((market_val - cost) / cost * 100) if cost > 0 else 0
        
        total_market += market_val
        
        position_data.append({
            'Product': product[:25],
            'Aantal': f"{qty:.4f}",
            'Kostprijs': f"€{cost:,.0f}",
            'Live': f"€{price:.2f}" if price else '-',
            'Waarde': f"€{market_val:,.0f}",
            'Rendement': f"{rendement:+.1f}%"
        })
    
    # KPIs
    rendement_total = ((total_market - total_cost) / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💼 Totaal Investering", f"€{total_cost:,.0f}")
    col2.metric("📈 Huidige Waarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", f"{rendement_total:+.1f}%")
    
    # Tabel
    st.markdown("### 💼 **Je Posities**")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

else:
    st.info("👆 **Upload je DEGIRO CSV** (Rekeningoverzicht → Export)")
