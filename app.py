import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("🔥 DEGIRO Dashboard - DEBUG MODE")

uploaded_file = st.file_uploader("Upload je DEGIRO CSV", type=None)

if uploaded_file is not None:
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")
    
    # Lees CSV
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=',')
    
    # === 1. TOON EXACT wat Pandas ziet ===
    st.subheader("📋 1. RUWE DATA (eerste 10 rijen)")
    st.dataframe(df[['Datum', 'Product', 'Mutatie', 'Saldo']].head(10))
    
    # === 2. TOON EXACT wat er in Mutatie/Saldo staat ===
    st.subheader("🔬 2. RAW WAARDEN in Mutatie & Saldo kolommen")
    st.write("**Mutatie kolom (eerste 15 rijen, exact zoals Pandas ze ziet):**")
    for i, val in enumerate(df['Mutatie'].head(15)):
        st.write(f"Rij {i}: '{val}' → type: {type(val)}")
    
    st.write("**Saldo kolom (eerste 5 rijen):**")
    for i, val in enumerate(df['Saldo'].head(5)):
        st.write(f"Rij {i}: '{val}' → type: {type(val)}")
    
    # === 3. TEST conversie op 1 waarde ===
    st.subheader("🧪 3. TEST: Probeer 1 waarde te converteren")
    test_value = df['Mutatie'].iloc[0] if len(df) > 0 else None
    st.write(f"**Testen met eerste Mutatie waarde:** '{test_value}'")
    
    def convert_nl_number(value):
        st.write(f"  Input: '{value}' (type: {type(value)})")
        if pd.isna(value) or str(value).strip() == '':
            result = 0.0
        else:
            s = str(value).strip()
            st.write(f"  Na strip: '{s}'")
            s = s.replace('.', '')  
            st.write(f"  Na replace '.': '{s}'")
            s = s.replace(',', '.') 
            st.write(f"  Na replace ',': '{s}'")
            try:
                result = float(s)
                st.write(f"  ✅ SUCCES: {result}")
            except Exception as e:
                st.write(f"  ❌ FOUT: {e}")
                result = 0.0
        return result
    
    test_result = convert_nl_number(test_value)
    st.metric("Test conversie resultaat", test_result)
    
    # === 4. ALLE waardes testen ===
    st.subheader("🧪 4. EERSTE 5 Mutatie waardes testen")
    for i in range(min(5, len(df))):
        val = df['Mutatie'].iloc[i]
        result = convert_nl_number(val)
        st.metric(f"Rij {i}", result)
    
else:
    st.info("👆 Upload je CSV!")
