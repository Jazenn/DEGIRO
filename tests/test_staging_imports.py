"""Synthetic rehearsal CLI: reject unsafe destinations before any connection."""
import os
import subprocess
import sys
import pytest


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
