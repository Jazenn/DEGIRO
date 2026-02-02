import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="DEGIRO Dashboard", layout="wide")

st.title("DEGIRO CSV Dashboard (simpel prototype)")

st.write(
    "Upload je DEGIRO-rekeningoverzicht (CSV) om basisinzichten te zien. "
    "Dit is een simpele start die je later kunt uitbreiden."
)

uploaded_file = st.file_uploader("Upload DEGIRO CSV", type=["csv"])

if uploaded_file is not None:
    # Probeer CSV in te lezen met ; of , als separator
    try:
        df = pd.read_csv(uploaded_file, sep=";")
    except Exception:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=",")

    st.subheader("Ruwe data")
    st.dataframe(df)

    # Probeer kolomnamen te normaliseren (DEGIRO NL export)
    # Vaak zijn er kolommen zoals: Datum, Tijd, Product, ISIN, Omschrijving, Mutatie, Saldo
    cols = {c.lower(): c for c in df.columns}

    # Helper om veilig een kolom op te halen
    def get_col(name):
        return cols.get(name.lower())

    date_col = get_col("Datum")
    product_col = get_col("Product")
    mutatie_col = get_col("Mutatie")
    saldo_col = get_col("Saldo")

    # Converteer datum
    if date_col is not None:
        df["__DatumParsed"] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
        df = df.sort_values("__DatumParsed")

    # Converteer Mutatie en Saldo van NL notatie "100,00" naar float
    for col_name in [mutatie_col, saldo_col]:
        if col_name is not None:
            df[col_name + "_num"] = (
                df[col_name]
                .astype(str)
                .str.replace(".", "", regex=False)   # duizendtallen weg
                .str.replace(",", ".", regex=False)  # komma naar punt
            )
            df[col_name + "_num"] = pd.to_numeric(df[col_name + "_num"], errors="coerce")

    st.markdown("---")
    st.subheader("Eenvoudige inzichten")

    # 1) Aantal transacties per product
    if product_col is not None:
        st.markdown("### Aantal transacties per product")
        counts = df[product_col].value_counts().reset_index()
        counts.columns = ["Product", "Aantal transacties"]
        st.dataframe(counts)

        fig1, ax1 = plt.subplots()
        ax1.bar(counts["Product"], counts["Aantal transacties"])
        ax1.set_xlabel("Product")
        ax1.set_ylabel("Aantal transacties")
        ax1.set_title("Transacties per product")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig1)
    else:
        st.info("Kolom 'Product' is niet gevonden; controleer of je de juiste DEGIRO-export gebruikt.")

    # 2) Saldo over tijd (indien beschikbaar)
    if date_col is not None and saldo_col is not None:
        st.markdown("### Saldo over tijd (zoals in CSV)")

        df_saldo = df.dropna(subset=["__DatumParsed", saldo_col + "_num"])
        if not df_saldo.empty:
            fig2, ax2 = plt.subplots()
            ax2.plot(df_saldo["__DatumParsed"], df_saldo[saldo_col + "_num"], marker="o")
            ax2.set_xlabel("Datum")
            ax2.set_ylabel("Saldo (EUR)")
            ax2.set_title("Saldo verloop volgens DEGIRO CSV")
            plt.xticks(rotation=45, ha="right")
            st.pyplot(fig2)
        else:
            st.info("Kon geen geldige data voor saldo over tijd vinden.")
    else:
        st.info("Datum- en/of Saldo-kolom niet gevonden; grafiek kan niet worden getoond.")

    # 3) Totale mutatie (netto in/out)
    if mutatie_col is not None:
        st.markdown("### Netto mutatie (som van alle mutaties)")
        total_mut = df[mutatie_col + "_num"].sum()
        st.metric("Totaal mutatie (EUR)", f"{total_mut:,.2f}")
    else:
        st.info("Kolom 'Mutatie' niet gevonden; netto mutatie kan niet worden berekend.")

else:
    st.info("Upload een DEGIRO CSV-bestand om te beginnen.")
