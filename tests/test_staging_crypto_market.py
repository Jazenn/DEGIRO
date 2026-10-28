"""Staging job uses external HTTP/database transports without private records."""
import pytest
import io
import json
from datetime import datetime, timedelta, timezone


def staging_environment(monkeypatch):
    values = {
        'STAGING_PUBLISHER_DATABASE_URL': 'postgresql://owner:synthetic-password@ep-staging-only.neon.tech/neondb?sslmode=require',
        'STAGING_EXPECTED_HOST': 'ep-staging-only.neon.tech',
        'STAGING_EXPECTED_DATABASE': 'neondb',
        'STAGING_CRYPTO_HISTORY_APPROVED': 'synthetic-staging-only',
        'COINGECKO_DEMO_API_KEY': 'synthetic-demo-key-never-print',
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize('override', [
    {'COINGECKO_DEMO_API_KEY': ''},
    {'STAGING_CRYPTO_HISTORY_APPROVED': ''},
    {'STAGING_EXPECTED_HOST': 'another.neon.tech'},
    {'STAGING_EXPECTED_DATABASE': 'another-database'},
])
def test_staging_crypto_job_rejects_missing_key_or_unapproved_destination_before_connection(monkeypatch, capsys, override):
    import psycopg2
    from backend.staging_crypto_market import main
    staging_environment(monkeypatch)
    for key, value in override.items():
        monkeypatch.setenv(key, value)

    def forbidden(*args, **kwargs):
        raise AssertionError('Unsafe configuration must not begin a connection')

    monkeypatch.setattr(psycopg2, 'connect', forbidden)
    assert main() == 1
    output = capsys.readouterr()
    assert 'destination_or_key_rejected' in output.out
    assert 'synthetic-password' not in output.out + output.err
    assert 'synthetic-demo-key-never-print' not in output.out + output.err


def test_complete_daily_publication_is_independent_and_incomplete_coin_retains_prior_series(monkeypatch):
    from backend.crypto_market import publish_market_history
    now = '2026-10-28T13:00:00Z'
    midnight = datetime(2026, 10, 28, tzinfo=timezone.utc)
    samples = [[int((midnight - timedelta(days=n)).timestamp() * 1000), 100 + n]
               for n in range(365)]
    requests = []

    def public_http(request, timeout):
        requests.append(request)
        incomplete = '/ethereum/' in request.full_url
        return io.BytesIO(json.dumps({'prices': samples[:-1] if incomplete else samples}).encode())

    monkeypatch.setattr('urllib.request.urlopen', public_http)
    prior = {'old-observation': {'source': 'previous verified series'}}
    stored = {'BTC-EUR': prior.copy(), 'ETH-EUR': prior.copy()}
    diagnostics = {}

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def execute(self, statement, params):
            coin, _, observations, _, reasons, _ = params
            if observations is not None:
                stored[coin] = observations.adapted
            diagnostics[coin] = reasons.adapted

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass

    results = publish_market_history(Connection(), now=now,
                                     api_key='synthetic-demo-key', require_complete=True)
    assert results['BTC-EUR'] == {'state': 'published', 'completed_days': '365'}
    assert results['ETH-EUR']['state'] == 'retained'
    assert len(stored['BTC-EUR']) == 365
    assert stored['ETH-EUR'] == prior
    assert diagnostics['ETH-EUR'] == ['complete_daily_window_required_previous_series_retained']
    assert len(requests) == 2
    assert all(request.get_header('X-cg-demo-api-key') == 'synthetic-demo-key' for request in requests)
