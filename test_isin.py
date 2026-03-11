import yfinance as yf
def test_isin():
    # test search
    import requests
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q=IE000OJ5TQP4"
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    print(r.json())

if __name__ == '__main__':
    test_isin()
