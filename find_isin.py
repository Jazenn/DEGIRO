import pandas as pd
import toml
from drive_utils import DriveStorage
import yfinance as yf

def find_isin():
    with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
        secrets = toml.load(f)
        creds = secrets.get("connections", {}).get("gsheets", {})
    
    DRIVE_FOLDER_ID = "16Y7kU4XDSbDjMUfBWU5695FSUWYjq26N"
    drive = DriveStorage(creds, DRIVE_FOLDER_ID)
    df = drive.load_data()

    print(df[["product", "isin"]].drop_duplicates())
            
if __name__ == '__main__':
    find_isin()
