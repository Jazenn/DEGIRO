
import pandas as pd
import io

def load_degiro_csv_debug(file_path):
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path)
    
    # Mimic app.py logic
    df.columns = [c.strip() for c in df.columns]
    
    rename_map = {
        "Datum": "date",
        "Tijd": "time",
        "Valutadatum": "value_date",
        "Product": "product",
        "ISIN": "isin",
        "Omschrijving": "description",
        "Mutatie": "amount",
        "Saldo": "balance",
        "FX": "fx",
        "Order Id": "order_id",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    print("Columns after rename:", df.columns.tolist())
    if "time" in df.columns:
        print("Sample Time column:", df["time"].head().tolist())
    
    for col in ["date", "value_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            
    # NEW: Combine Date and Time
    if "date" in df.columns and "time" in df.columns:
        print("Attempting to combine Date + Time...")
        try:
            d_str = df["date"].astype(str).str.split(" ").str[0]
            if pd.api.types.is_datetime64_any_dtype(df["date"]):
                 d_str = df["date"].dt.strftime("%Y-%m-%d")
            
            t_str = df["time"].astype(str)
            
            # Debug the string combination
            combined_str = d_str + " " + t_str
            print("Sample combined strings:", combined_str.head().tolist())
            
            full_dt = pd.to_datetime(combined_str, errors="coerce")
            print("Sample parsed datetimes:", full_dt.head().tolist())
            
            df["value_date"] = full_dt.fillna(df["value_date"])
            
        except Exception as e:
            print(f"Error combining: {e}")
            
    return df

# Run on the file
try:
    df_result = load_degiro_csv_debug("Account_test1.csv")
    print("\nFinal value_date sample:")
    print(df_result[["date", "time", "value_date"]].head(10))
    
    # Check specifically for the Bitcoin transaction on 30-01
    btc_tx = df_result[df_result["description"].fillna("").str.contains("BITCOIN", case=False)]
    if not btc_tx.empty:
        print("\nBitcoin Transactions:")
        print(btc_tx[["date", "time", "value_date", "description"]])
    else:
        print("\nNo Bitcoin transactions found.")

except Exception as e:
    with open("debug_output_py.txt", "w", encoding="utf-8") as f:
        f.write(f"Script failed: {e}\n")

if 'df_result' in locals():
    with open("debug_output_py.txt", "w", encoding="utf-8") as f:
        f.write("Columns after rename: " + str(df_result.columns.tolist()) + "\n")
        f.write("\nFinal value_date sample:\n")
        f.write(df_result[["date", "time", "value_date"]].head(10).to_string() + "\n")
        
        # Check specifically for the Bitcoin transaction on 30-01
        btc_tx = df_result[df_result["description"].fillna("").str.contains("BITCOIN", case=False)]
        if not btc_tx.empty:
            f.write("\nBitcoin Transactions:\n")
            f.write(btc_tx[["date", "time", "value_date", "description"]].to_string() + "\n")
        else:
            f.write("\nNo Bitcoin transactions found.\n")
