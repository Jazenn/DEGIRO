import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

st.set_page_config(page_title="DEGIRO Inzichten", layout="wide")

st.title("🧠 DEGIRO Account Inzichten")
st.markdown("Upload je DEGIRO rekeningoverzicht CSV voor analyses.")

# Tolerante file uploader met fallback
st.subheader("📁 Upload DEGIRO CSV")
col1, col2 = st.columns([3,1])
with col1:
    uploaded_file = st.file_uploader("Kies CSV", type="csv", help="DEGIRO Account.csv ondersteund")
with col2:
    max_size_mb = st.slider("Max size (MB)", 10, 500, 200)

# Sample data voor testen
if st.checkbox("🧪 Gebruik testdata (geen upload nodig)"):
    sample_data = """Datum;Tijd;Product;ISIN;Aantal;Koers;Waarde EUR;Totaal EUR
01-01-2026;10:00;VWCE DE;IE00BK5BQT80;10;120.50;1205.00;1205.00
15-01-2026;14:30;Apple Inc.;US0378331005;5;180.20;901.00;901.00
20-01-2026;09:15;ASML;NL0010273215;2;850.75;1701.50;1701.50"""
    uploaded_file = io.StringIO(sample_data)

@st.cache_data
def load_data(file):
    """Robuuste CSV parser voor DEGIRO format"""
    encodings = ['utf-8', 'latin1', 'iso-8859-1']
    separators = [';', ',']
    
    for encoding in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(file, sep=sep, encoding=encoding)
                if len(df) > 0:
                    return df
            except:
                continue
    raise ValueError("Kan CSV niet parsen. Probeer UTF-8 encoding en ';' separator.")

if uploaded_file is not None:
    # File size check
    if hasattr(uploaded_file, 'size') and uploaded_file.size > max_size_mb * 1024 * 1024:
        st.error(f"❌ File te groot: {uploaded_file.size / (1024*1024):.1f} MB > {max_size_mb} MB")
    else:
        # Progress bar
        progress = st.progress(0)
        status = st.empty()
        
        try:
            df = load_data(uploaded_file)
            progress.progress(50)
            status.info("📊 Parsing kolommen...")
            
            st.success(f"✅ Geladen: {len(df)} transacties")
            
            # Data preview
            st.subheader("📋 Data Voorbeeld")
            st.dataframe(df.head(10), use_container_width=True)
            
            progress.progress(75)
            
            # Flexibele kolom detectie (DEGIRO NL)
            col_date = next((col for col in df.columns if any(x in col.lower() for x in ['datum', 'date', 'tijd'])), None)
            col_product = next((col for col in df.columns if any(x in col.lower() for x in ['product', 'naam', 'isin'])), None)
            col_quantity = next((col for col in df.columns if any(x in col.lower() for x in ['aantal', 'quantity'])), None)
            col_price = next((col for col in df.columns if any(x in col.lower() for x in ['koers', 'price'])), None)
            col_value = next((col for col in df.columns if any(x in col.lower() for x in ['waarde', 'value', 'totaal', 'total'])), None)
            
            st.info(f"🔍 Gedetecteerde kolommen: Datum={col_date}, Product={col_product}, Aantal={col_quantity}, Waarde={col_value}")
            
            if all([col_date, col_product, col_quantity, col_value]):
                progress.progress(90)
                
                # Data processing
                df['Datum'] = pd.to_datetime(df[col_date].astype(str), errors='coerce', dayfirst=True)
                df['Product'] = df[col_product].fillna('Onbekend')
                df['Quantity'] = pd.to_numeric(df[col_quantity], errors='coerce')
                df['Value_EUR'] = pd.to_numeric(df[col_value].astype(str).str.replace(',', '.').str.replace('.', '', regex=False), errors='coerce')
                
                df_clean = df.dropna(subset=['Datum', 'Value_EUR']).copy()
                
                # Tabs met inzichten
                tab1, tab2, tab3, tab4 = st.tabs(["📈 Transacties", "💼 Holdings", "📊 Grafieken", "💰 Samenvatting"])
                
                with tab1:
                    st.subheader("Recente Transacties")
                    st.dataframe(
                        df_clean[['Datum', 'Product', 'Quantity', 'Value_EUR']].sort_values('Datum', ascending=False).head(50),
                        use_container_width=True
                    )
                
                with tab2:
                    st.subheader("Huidige Posities")
                    holdings = df_clean.groupby('Product')['Quantity'].sum().reset_index()
                    holdings['Abs_Quantity'] = holdings['Quantity'].abs()
                    holdings = holdings[holdings['Abs_Quantity'] > 0].sort_values('Abs_Quantity', ascending=False)
                    st.dataframe(holdings, use_container_width=True)
                
                with tab3:
                    st.subheader("Visualisaties")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig1 = px.bar(
                            df_clean.head(20), 
                            x='Product', 
                            y='Value_EUR', 
                            color='Quantity',
                            title="Top 20 Transacties",
                            color_continuous_scale='RdYlGn'
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                    
                    with col2:
                        fig2 = px.pie(
                            df_clean.groupby('Product')['Value_EUR'].sum().reset_index(),
                            values='Value_EUR',
                            names='Product',
                            title="Transacties per Product"
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                
                with tab4:
                    st.subheader("Key Metrics")
                    total_volume = df_clean['Value_EUR'].sum()
                    avg_trade = df_clean['Value_EUR'].mean()
                    num_trades = len(df_clean)
                    unique_products = df_clean['Product'].nunique()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.metric("Totaal Volume", f"€{total_volume:,.0f}")
                    with col2: st.metric("Gem. Transactie", f"€{avg_trade:,.0f}")
                    with col3: st.metric("Aantal Trades", num_trades)
                    with col4: st.metric("Producten", unique_products)
                
                progress.progress(100)
                status.success("🎉 Analyse voltooid!")
                
            else:
                st.warning("⚠️ Kan geen standaard DEGIRO kolommen vinden.")
                st.info("Typische kolommen: 'Datum/Tijd', 'Product', 'Aantal', 'Waarde EUR/Totaal EUR'")
                
        except Exception as e:
            st.error(f"❌ Fout: {str(e)}")
            st.info("Tips:\n- Open CSV in Notepad++, Save As → UTF-8 zonder BOM\n- Controleer separator (meestal ';')\n- Verwijder lege rijen bovenaan")

# Alternatieve input methode
st.subheader("🆘 Alternatief: Plak CSV tekst")
csv_text = st.text_area("Plak CSV content hier (eerste 1000 regels)", height=150)
if st.button("Parse geplakte tekst") and csv_text.strip():
    try:
        df = pd.read_csv(io.StringIO(csv_text), sep=';', encoding='utf-8')
        st.success(f"✅ {len(df)} rijen geparsed!")
        st.dataframe(df.head())
    except:
        try:
            df = pd.read_csv(io.StringIO(csv_text), sep=',', encoding='latin1')
            st.success(f"✅ {len(df)} rijen geparsed!")
            st.dataframe(df.head())
        except Exception as e:
            st.error(f"Parse fout: {e}")

st.markdown("---")
st.caption("💡 Tip: Exporteer via DEGIRO → Service → Rekeningoverzicht → CSV")
