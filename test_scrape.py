
import re
import requests

def fetch_tradegate_price(isin: str) -> float | None:
    try:
        url = f"https://www.tradegate.de/orderbuch.php?isin={isin}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code != 200:
            return None
        
        match = re.search(r'id="last"[^>]*>\s*([\d.,]+)\s*<', resp.text)
        if match:
            price_str = match.group(1).replace(".", "").replace(",", ".")
            return float(price_str)
    except Exception as e:
        print(f"Error scraping {isin}: {e}")
    return None

isins = ["IE00BK5BQT80", "IE000OJ5TQP4"] # VWCE, FOD
for isin in isins:
    p = fetch_tradegate_price(isin)
    print(f"ISIN {isin}: {p}")
