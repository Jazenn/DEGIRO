"""Official adapter contract exercised with invented holdings, never private records."""
import json
from pathlib import Path
import pytest

from backend.exposure import build_exposure
from backend.exposure_sources import load_sources


URL = 'https://www.ishares.com/uk/individual/en/products/251861/ishares-core-msci-europe-ucits-etf-eur-acc/latest-holdings.csv'
FUND = 'IE00B4K48X80'


def test_reviewed_ishares_source_keeps_residual_and_unknown_ids_through_exposure(tmp_path, monkeypatch):
    source = Path(__file__).parent / 'fixtures/ishares_synthetic_holdings.csv'

    class Response:
        status_code = 200
        headers = {'Content-Type': 'text/plain; charset=utf-8'}

        def __enter__(self): return self
        def __exit__(self, *args): return None
        def raise_for_status(self): pass
        def iter_content(self, size): yield source.read_bytes()

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr('requests.get', get)
    manifest = tmp_path / 'sources.json'
    manifest.write_text(json.dumps({FUND: {'adapter': 'ishares-csv', 'url': URL}}))
    sources = load_sources(manifest)
    result = build_exposure({'ledger': {'market_value_eur': '1000', 'positions': [
        {'broker_asset_id': FUND, 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '1000'},
    ]}}, sources)
    fund = result['funds'][0]
    assert calls == [(URL, {'timeout': 20, 'stream': True, 'allow_redirects': False})]
    assert fund['provider'] == 'iShares'
    assert fund['as_of'] == '2026-10-27'
    assert fund['state'] == 'partial'
    assert fund['covered_reported_fraction'] == '0.9997'
    assert fund['covered_fund_fraction'] is None
    assert fund['portfolio_fraction'] is None
    assert fund['countries'] == {'Germany': '29.97', 'Netherlands': '70.00'}
    assert fund['identifier_namespace'] is None
    assert all(row['security_id'] is None for row in fund['holdings'])
    assert result['covered_portfolio_fraction'] == '0'


@pytest.mark.parametrize('fund,url', [
    ('IE00BK5BQT80', URL),
    (FUND, URL.replace('www.ishares.com', 'provider.example')),
    (FUND, URL + '?redirect=elsewhere'),
    (FUND, URL.replace('https://', 'https://user:password@')),
])
def test_ishares_fund_identity_and_exact_official_url_are_checked_before_request(tmp_path, monkeypatch, fund, url):
    def unexpected(*args, **kwargs):
        raise AssertionError('Unapproved source must not be fetched')

    monkeypatch.setattr('requests.get', unexpected)
    manifest = tmp_path / 'sources.json'
    manifest.write_text(json.dumps({fund: {'adapter': 'ishares-csv', 'url': url}}))
    with pytest.raises(ValueError, match='Unapproved official source URL'):
        load_sources(manifest)


@pytest.mark.parametrize('change', ['date', 'schema', 'negative', 'overweight', 'html', 'size', 'redirect'])
def test_invalid_ishares_disclosures_never_produce_exposure(tmp_path, monkeypatch, change):
    text = (Path(__file__).parent / 'fixtures/ishares_synthetic_holdings.csv').read_text()
    if change == 'date': text = text.replace('27/Oct/2026', '31/Feb/2026')
    if change == 'schema': text = text.replace('Weight (%)', 'Unknown weight')
    if change == 'negative': text = text.replace('"29.97"', '"-0.01"')
    if change == 'overweight': text = text.replace('"29.97"', '"30.01"')

    class Response:
        status_code = 302 if change == 'redirect' else 200
        headers = {'Content-Type': 'text/html' if change == 'html' else 'text/plain'}

        def __enter__(self): return self
        def __exit__(self, *args): return None
        def raise_for_status(self): pass
        def iter_content(self, size): yield b'x' * (2 * 1024 * 1024 + 1) if change == 'size' else text.encode()

    monkeypatch.setattr('requests.get', lambda *args, **kwargs: Response())
    manifest = tmp_path / 'sources.json'
    manifest.write_text(json.dumps({FUND: {'adapter': 'ishares-csv', 'url': URL}}))
    with pytest.raises(ValueError):
        load_sources(manifest)
