import requests
import json

isin = "IE00BK5BQT80" # VWCE
url = f"https://www.tradegate.de/refresh.php?isin={isin}"
headers = {'User-agent': 'Mozilla/5.0'}

try:
    r = requests.get(url, headers=headers, timeout=5)
    print("TradeGate refresh.php response:")
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
