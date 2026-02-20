import requests, json

url = 'https://query2.finance.yahoo.com/v1/finance/search?q=IE00B4K48X80'
r = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
quotes = r.json().get('quotes', [])
res = [{'symbol': q.get('symbol'), 'exchange': q.get('exchange'), 'shortname': q.get('shortname')} for q in quotes]
with open('check_eunk.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=2)
