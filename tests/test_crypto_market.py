import io
import json
import urllib.request

from backend.crypto_market import fetch_market_coin


def test_public_market_adapter_discards_live_tail_without_private_portfolio_configuration(monkeypatch):
    def public_http(request, timeout):
        assert '/coins/bitcoin/market_chart?' in request.full_url
        assert 'vs_currency=eur' in request.full_url
        assert 'days=365' in request.full_url
        return io.BytesIO(json.dumps({'prices': [
            [1792627200000, 100],  # 22 October 2026 at00:00 closes21October
            [1792713600000, 110],  # 23 October at00:00 closes22October
            [1792756800000, 999],  # live noon point must be excluded
        ]}).encode())
    monkeypatch.setattr(urllib.request, 'urlopen', public_http)
    rows = fetch_market_coin('BTC-EUR', now='2026-10-23T13:00:00Z')
    assert set(rows) == {'2026-10-22T00:00:00Z', '2026-10-23T00:00:00Z'}
    assert rows['2026-10-23T00:00:00Z']['price_eur'] == '110'
    assert rows['2026-10-23T00:00:00Z']['currency'] == 'EUR'
