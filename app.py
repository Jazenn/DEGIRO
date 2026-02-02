import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("📈 DeGiro Portfolio Dashboard")

st.write("""
Upload hier je DeGiro exportbestand (CSV of TXT).
""")

uploaded_file = st.file_uploader(
    "Kies je DeGiro exportbestand",
    accept_multiple_files=False
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.subheader("Originele Data (preview)")
    st.dataframe(df.head())

    df['Datum'] = pd.to_datetime(df['Datum'], format='%d-%m-%Y')

    df['Mutatie'] = df['Mutatie'].astype(str).str.replace('.', '', regex=False)
    df['Mutatie'] = df['Mutatie'].str.replace(',', '.', regex=False)
    df['Mutatie'] = pd.to_numeric(df['Mutatie'], errors='coerce')

    df = df.sort_values('Datum')

    df['Cumulatief'] = df['Mutatie'].cumsum()

    timeline = df.groupby('Datum')['Cumulatief'].last().reset_index()

    st.subheader("📊 Portfolio Waarde Over Tijd")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(timeline['Datum'], timeline['Cumulatief'])
    ax.set_title("Portfolio Ontwikkeling")
    ax.set_xlabel("Datum")
    ax.set_ylabel("Waarde (€)")
    plt.xticks(rotation=45)

    st.pyplot(fig)

    st.subheader("📌 Samenvatting")

    totaal_gestort = df[df['Mutatie'] > 0]['Mutatie'].sum()
    totaal_opgenomen = abs(df[df['Mutatie'] < 0]['Mutatie'].sum())
    netto_resultaat = df['Mutatie'].sum()

    col1, col2, col3 = st.columns(3)

    col1.metric("Totaal Gestort", f"€ {totaal_gestort:,.2f}")
    col2.metric("Totaal Opgenomen", f"€ {totaal_opgenomen:,.2f}")
    col3.metric("Netto Resultaat", f"€ {netto_resultaat:,.2f}")

    st.subheader("Volledige Transacties")
    st.dataframe(df)

else:
    st.info("Upload eerst je DeGiro exportbestand om te beginnen.")
