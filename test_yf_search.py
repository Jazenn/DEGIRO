import requests
import json
import urllib.parse

def search_yf(query):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}"
    headers = {'User-agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers)
        data = r.json()
        return data.get('quotes', [])
    except Exception as e:
        return {"error": str(e)}

results = {
    'IE00BK5BQT80': search_yf('IE00BK5BQT80'),
    'VWCE': search_yf('VWCE'),
    'VANGUARD FTSE ALL-WORLD': search_yf('VANGUARD FTSE ALL-WORLD'),
    'APPLE INC': search_yf('APPLE INC.O'),
    'NVIDIA': search_yf('NVIDIA')
}

with open('search_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
