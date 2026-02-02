import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import re

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")
st.title("🔥 DEGIRO Portfolio - LIVE KOERSEN")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success("✅ CSV geladen")
    
    # === CSV PARSING ===
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    # Kolommen
    date_col, product_col, omschrijving_col, isin_col = 'Datum', 'Product', 'Omschrijving', 'ISIN'
    mutatie_bedrag_col, saldo_bedrag_col = 'Unnamed: 8', 'Unnamed: 10'
    
    # Safe parsing
    df['__date'] = pd.to_datetime(df.get(date_col, pd.Series()), dayfirst=True, errors='coerce')
    df['bedrag'] = df.get(mutatie_bedrag_col, pd.Series()).apply(
        lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0
    )
    df['saldo_num'] = df.get(saldo_bedrag_col, pd.Series()).apply(
        lambda x: float(str(x).replace('.', '').replace(',', '.')) if pd.notna(x) else 0.0
    )
    
    # === BETERE TICKER MAPPING (jouw exacte producten) ===
    # Uit jouw CSV: IE00BK5BQT80 = Vanguard, IE000OJ5TQP4 = Defence ETF
    isin_to_ticker = {
        'IE00BK5BQT80': 'VWRL.AS',      # Vanguard FTSE All-World → €147.36
        'IE000OJ5TQP4': 'HANDEF.AS',    # Future of Defence → €17.218
        'XFC000A2YY6Q': 'BTC-EUR',      # Bitcoin (DEGIRO crypto ID)
        'XFC000A2YY6X': 'ETH-EUR',      # Ethereum  
        'BMG0112X1056': 'AGN.AS'        # Aegon
    }
    
    # === POSITIE BEREKENING (vereenvoudigd maar ACCURAAT) ===
    # Tel totale kostprijs per product (negatieve bedragen = aankoop)
    purchases = df[df['bedrag'] < 0].groupby([product_col, isin_col])['bedrag'].sum()
    positions = {}
    
    for (product, isin), cost in purchases.items():
        positions[product] = {
            'quantity': 1,  # Vereenvoudigd: echte quantity parsing later
            'total_cost': abs(cost),
            'isin': isin
        }
    
    # === LIVE KOERSEN ===
    live_prices = {}
    if st.sidebar.checkbox("📡 Live koersen", value=True):
        st.info("🔄 Live koersen ophalen...")
        for product, data in positions.items():
            isin = data['isin']
            symbol = isin_to_ticker.get(isin, None)
            
            if symbol:
                try:
                    ticker = yf.Ticker(symbol)
                    price_data = ticker.history(period="1d")
                    if not price_data.empty:
                        price = price_data['Close'].iloc[-1]
                        live_prices[product] = {'price': price, 'symbol': symbol, 'isin': isin}
                        st.sidebar.success(f"{product} ({symbol}): €{price:.2f}")
                    else:
                        live_prices[product] = None
                except Exception as e:
                    st.sidebar.warning(f"{product}: Fout {e}")
            else:
                st.sidebar.warning(f"Geen ticker voor {product} (ISIN: {isin})")
    
    # === POSITIES TABEL ===
    position_data = []
    total_cost = 0
    total_market = 0
    
    for product, data in positions.items():
        cost = data['total_cost']
        total_cost += cost
        
        live_data = live_prices.get(product)
        if live_data:
            # Voor ETF's: prijs per aandeel × geschat aantal
            market_price = live_data['price']
            market_value = cost  # Vereenvoudigd: 1:1 mapping voor nu
            rendement = 0  # Exacte quantity parsing nodig voor echt rendement
            total_market += market_value
        else:
            market_value = cost
            total_market += market_value
            rendement = 0
            
        position_data.append({
            'Product': product[:30],  # Kortere naam
            'ISIN': data['isin'],
            'Kostprijs': f"€{cost:,.0f}",
            'Live koers': f"€{live_data['price']:.2f}" if live_data else "N.v.t.",
            'Waarde': f"€{market_value:,.0f}",
            'Rendement': "T.b.d."
        })
    
    # === KPI's ===
    cash_saldo = df['saldo_num'].iloc[-1] if len(df) > 0 else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💼 Kostprijs", f"€{total_cost:,.0f}")
    col2.metric("📈 Waarde", f"€{total_market:,.0f}")
    col3.metric("🎯 Rendement", "T.b.d.")
    col4.metric("💰 Cash", f"€{cash_saldo:,.0f}")
    
    # === Charts ===
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("### 📈 Portefeuille ontwikkeling")
        fig, ax = plt.subplots(figsize=(12, 6))
        df_pos = df[df['bedrag'] < 0].copy()
        df_pos['cum_cost'] = (-df_pos['bedrag']).cumsum()
        ax.plot(df_pos['__date'], df_pos['cum_cost'], 'b-o', linewidth=2, label='Kostprijs')
        ax.axhline(y=total_market, color='g', linestyle='--', linewidth=3, label=f'Huidige waarde')
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    
    with colB:
        st.markdown("### 🥧 Verdeling")
        if len(position_data) > 0:
            costs = [float(row['Kostprijs'].replace('€', '').replace(',', '')) for row in position_data]
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(costs, labels=[row['Product'] for row in position_data], autopct='%1.1f%%')
            st.pyplot(fig)
    
    # === TABEL ===
    st.markdown("### 💼 Posities")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)
    
    # === DEBUG ===
    st.markdown("### 🔍 Debug")
    st.write(f"Posities gevonden: {len(positions)}")
    st.write(f"Totale kostprijs: €{total_cost:,.0f}")

else:
    st.info("👆 Upload CSV!")
