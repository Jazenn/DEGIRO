import pytest
from backend.import_jobs import stage_generation


CSV = (b'Date,Time,Product,ISIN,Description,Amount,,Order Id\n'
       b'02-01-2026,09:00,,,Deposit,EUR,1005,\n')
SETTINGS = {'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic'},
            'cost_history': {'verified': True, 'evidence': 'synthetic'},
            'opening_baseline': {'at': '2026-01-01T00:00:00Z', 'cash_eur': '0',
                                 'equity_eur': '0', 'verified': True, 'evidence': 'synthetic'}}


def test_repeated_upload_publishes_one_canonical_cash_flow():
    result = stage_generation([CSV, CSV], settings=SETTINGS, quotes={}, cutoff='2026-01-10T00:00:00Z')
    assert result['ledger']['cash_balance_eur'] == '1005'
    assert result['ledger']['net_external_contributions_eur'] == '1005'


def test_invalid_upload_cannot_produce_a_generation():
    with pytest.raises(ValueError):
        stage_generation([CSV, b'not,a,supported,file'], settings=SETTINGS, quotes={}, cutoff='2026-01-10T00:00:00Z')
