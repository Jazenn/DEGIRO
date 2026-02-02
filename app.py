import streamlit as st
import pandas as pd

st.set_page_config(page_title="Test uploader", layout="centered")

st.title("Test: CSV upload")

st.write("Kies een CSV-bestand vanaf je computer.")

# Belangrijk: géén type-filter
uploaded_file = st.file_uploader("Upload een bestand")

st.write("Raw value van uploaded_file:", uploaded_file)

if uploaded_file is not None:
    st.success(f"Bestand ontvangen: {uploaded_file.name}")

    # Probeer CSV te lezen
    try:
        # reset pointer voor de zekerheid
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=None, engine="python")
        st.write("Eerste rijen van je CSV:")
        st.dataframe(df.head())
    except Exception as e:
        st.error(f"Kon het bestand niet als CSV lezen: {e}")
else:
    st.info("Nog geen bestand geüpload.")
