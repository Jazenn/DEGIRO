"""Recovery CLI must reject unapproved destinations before any database access."""
import os
import subprocess
import sys


def test_recovery_cli_rejects_unapproved_endpoint_without_exposing_credentials():
    environment = {**os.environ, 'STAGING_PUBLISHER_DATABASE_URL':
                   'postgresql://owner:never-print-this@other.example.test/neondb?sslmode=require',
                   'STAGING_EXPECTED_HOST': 'approved.example.test',
                   'STAGING_EXPECTED_DATABASE': 'neondb',
                   'STAGING_BRANCH_ID': 'br-tiny-moon-al8b0u31'}
    result = subprocess.run([sys.executable, '-m', 'backend.staging_recovery'],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout.strip() == 'Staging recovery rehearsal failed; credentials and database content withheld.'
    assert 'never-print-this' not in result.stdout + result.stderr
    assert result.stderr == ''


def test_recovery_cli_requires_real_postgres_clients_before_connecting(tmp_path):
    environment = {**os.environ, 'STAGING_PUBLISHER_DATABASE_URL':
                   'postgresql://owner:secret@ep-synthetic-only.neon.tech/neondb?sslmode=require',
                   'STAGING_EXPECTED_HOST': 'ep-synthetic-only.neon.tech',
                   'STAGING_EXPECTED_DATABASE': 'neondb',
                   'STAGING_BRANCH_ID': 'br-tiny-moon-al8b0u31',
                   'PG_BIN': str(tmp_path)}
    result = subprocess.run([sys.executable, '-m', 'backend.staging_recovery'],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout.strip() == 'Staging recovery rehearsal failed; credentials and database content withheld.'
    assert result.stderr == ''
