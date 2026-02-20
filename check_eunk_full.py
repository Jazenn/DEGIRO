import requests, json, urllib.parse

def search(query):
    url = f'https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}'
    r = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
    quotes = r.json().get('quotes', [])
    return [{'symbol': q.get('symbol'), 'exchange': q.get('exchange'), 'shortname': q.get('shortname')} for q in quotes]

results = {
    'Full Name': search('iShares Core MSCI Europe UCITS ETF EUR (Acc)')
}

with open('check_eunk_full.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
