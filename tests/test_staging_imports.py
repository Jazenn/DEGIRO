"""Synthetic rehearsal CLI: reject unsafe destinations before any connection."""
import os
import subprocess
import sys
import pytest


def assert_import_destination_rejected_before_connection(monkeypatch, capsys, override):
    import psycopg2
    from backend.staging_imports import main
    calls = []
    def forbidden_connection(*args, **kwargs):
        calls.append(True)
        raise AssertionError('No database connection may begin')
    monkeypatch.setattr(psycopg2, 'connect', forbidden_connection)
    values = {'STAGING_PUBLISHER_DATABASE_URL':
              'postgresql://owner:secret@ep-synthetic-only.neon.tech/neondb?sslmode=require'+('&'+override if override else ''),
              'STAGING_EXPECTED_HOST': 'ep-synthetic-only.neon.tech',
              'STAGING_EXPECTED_DATABASE': 'neondb',
              'STAGING_IMPORT_REHEARSAL_APPROVED': 'synthetic-staging-only'}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    assert main() == 1
    assert calls == []
    assert 'destination_rejected' in capsys.readouterr().out


@pytest.mark.parametrize('override', ['host=other.example', 'dbname=otherdb',
                                     'hostaddr=127.0.0.1', 'service=other'])
def test_import_rehearsal_rejects_libpq_destination_overrides_before_driver(monkeypatch, capsys, override):
    assert_import_destination_rejected_before_connection(monkeypatch, capsys, override)


def test_import_rehearsal_rejects_ambient_host_address_without_connection(monkeypatch, capsys):
    monkeypatch.setenv('PGHOSTADDR', '127.0.0.1')
    assert_import_destination_rejected_before_connection(monkeypatch, capsys, '')


def test_rehearsal_sources_reconcile_overlap_through_the_canonical_import_boundary():
    from backend.staging_imports import fixture
    from backend.import_jobs import stage_generation
    source, overlap, settings, quotes = fixture()
    model = stage_generation([source, overlap], settings=settings, quotes=quotes,
                             cutoff='2026-01-11T00:00:00Z')
    assert model['ledger']['cash_balance_eur'] == '0'
    assert model['ledger']['net_external_contributions_eur'] == '1005'
    assert model['ledger']['net_gain_eur'] == '95'
    assert model['ledger']['positions'][0]['retained_cost_eur'] == '1005'


@pytest.mark.parametrize('url,host,database,approval', [
    ('postgresql://owner:secret-never-print@wrong.example/staging', 'approved.example', 'staging', 'synthetic-staging-only'),
    ('postgresql://owner:secret-never-print@approved.example/production', 'approved.example', 'staging', 'synthetic-staging-only'),
    ('postgresql://owner:secret-never-print@approved-pooler.example/staging', 'approved-pooler.example', 'staging', 'synthetic-staging-only'),
    ('postgresql://owner:secret-never-print@approved.example/staging', 'approved.example', 'staging', ''),
])
def test_staging_rehearsal_rejects_unsafe_destination_without_exposing_credentials(url, host, database, approval):
    environment = {**os.environ,
                   'STAGING_PUBLISHER_DATABASE_URL': url,
                   'STAGING_EXPECTED_HOST': host,
                   'STAGING_EXPECTED_DATABASE': database,
                   'STAGING_IMPORT_REHEARSAL_APPROVED': approval}
    result = subprocess.run([sys.executable, '-m', 'backend.staging_imports'],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'destination_rejected' in result.stdout
    assert 'secret-never-print' not in result.stdout + result.stderr
    assert 'wrong.example' not in result.stdout + result.stderr
