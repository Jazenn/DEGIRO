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
            coin, _, observations, _, reasons, summary, _, _, _ = params
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


@pytest.mark.parametrize('complete', [True, False])
def test_publisher_prepares_same_version_exact_sorted_window_and_retains_on_failure(monkeypatch, complete):
    from backend.crypto_market import publish_market_history
    now = '2026-10-23T12:00:00Z'
    end = datetime(2026, 10, 23, tzinfo=timezone.utc)
    observations = {}
    for n in range(365):
        at = (end - timedelta(days=364-n)).isoformat().replace('+00:00', 'Z')
        observations[at] = {'price_eur': str(n+1), 'observed_at': at, 'retrieved_at': now,
                            'provider': 'synthetic', 'currency': 'EUR', 'adjustment_basis': 'unadjusted'}
    monkeypatch.setattr('backend.crypto_market.fetch_market_coin', lambda symbol, **kw: observations if symbol == 'BTC-EUR' else {})
    writes = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params): writes.append(params)
    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
    publish_market_history(Connection(), now=now, require_complete=complete)
    summary = writes[0][5].adapted
    assert summary['version'] == writes[0][1]
    assert summary['sorted_prices'] == [str(n) for n in range(1,366)]
    assert summary['context_prices'] == [str(n) for n in range(276,366)]
    assert summary['cutoff'] == '2026-10-23T00:00:00Z'
    assert writes[1][5] is None  # failed series retains prior matching summary

@pytest.mark.parametrize('change', [{'currency':'USD'}, {'adjustment_basis':'total_return'}, {'price_eur':'0'}, {'price_eur':'NaN'}, {'retrieved_at':'2099-01-01T00:00:00Z'}, {'observed_at':'2026-10-23T01:00:00Z'}, {'provider':'different'}])
@pytest.mark.parametrize('complete', [True, False])
def test_publisher_never_prepares_invalid_source_data(monkeypatch, change, complete):
    from backend.crypto_market import publish_market_history
    now = '2026-10-23T12:00:00Z'
    end = datetime(2026,10,23,tzinfo=timezone.utc)
    rows = {}
    for n in range(365):
        at = (end-timedelta(days=n)).isoformat().replace('+00:00','Z')
        rows[at] = {'price_eur':'100','observed_at':at,'retrieved_at':now,'currency':'EUR','adjustment_basis':'unadjusted','provider':'synthetic'}
    rows['2026-10-23T00:00:00Z'].update(change)
    monkeypatch.setattr('backend.crypto_market.fetch_market_coin', lambda *args, **kw: rows)
    writes=[]
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,sql,params): writes.append(params)
    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
    publish_market_history(Connection(),now=now,require_complete=complete)
    assert all(params[5] is None for params in writes)
    assert all((params[2] is None) == complete for params in writes)  # strict staging retains; legacy raw semantics preserved

@pytest.mark.parametrize('entrypoint', ['default_helper', 'main'])
@pytest.mark.parametrize('invalid_source', ['incomplete', 'corrupt'])
def test_normal_publisher_paths_retain_previous_generation_on_invalid_source(monkeypatch, entrypoint, invalid_source):
    import backend.crypto_market as market
    import psycopg2
    now = datetime.now(timezone.utc)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = {}
    for n in range(365):
        at = (end-timedelta(days=n)).isoformat().replace('+00:00','Z')
        rows[at] = {'price_eur':'100','observed_at':at,'retrieved_at':now.isoformat(),
                    'currency':'EUR','adjustment_basis':'unadjusted','provider':'synthetic'}
    if invalid_source == 'incomplete':
        rows.pop(next(iter(rows)))
    else:
        rows[next(iter(rows))]['currency'] = 'USD'
    monkeypatch.setattr(market, 'fetch_market_coin', lambda *args, **kw: rows)
    writes = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,sql,params): writes.append(params)
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def cursor(self): return Cursor()
        def commit(self): pass
    if entrypoint == 'main':
        monkeypatch.setenv('DATABASE_URL', 'synthetic-transport-only')
        monkeypatch.setattr(psycopg2, 'connect', lambda *args, **kw: Connection())
        market.main()
    else:
        result = market.publish_market_history(Connection(), now=now.isoformat())
        assert all(value['state'] == 'retained' for value in result.values())
    assert len(writes) == 2
    # SQL regression executes this NULL-source path and proves all three persist.
    assert all(params[2] is None and params[5] is None and params[8] is True for params in writes)
