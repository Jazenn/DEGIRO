import pytest
from backend.import_jobs import stage_generation, process_next


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

def test_import_pipeline_publishes_explicit_history_contract_without_fabricating_prices():
    result = stage_generation([CSV], settings=SETTINGS, quotes={}, cutoff='2026-01-10T00:00:00Z')
    assert result['portfolio_history']['periods'] == {}
    assert result['portfolio_history']['diagnostics'] == ['observed_daily_history_not_supplied']
    assert result['portfolio_history']['ledger_version'] == result['ledger_version']


class DatabaseTransport:
    """Database system boundary: racing commits become visible at locking reads.

    No canonical parser/calculator is mocked. Real SQL concurrency is a separate
    staged integration gate; this transport models transaction outcomes only.
    """
    def __init__(self, race=None, empty=False):
        self.race = race
        self.rows = []
        self.rowcount = 1
        self.generation = None if empty else 'accepted-before'
        self.target_version = '3'
        self.publication = None

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def commit(self):
        pass

    def rollback(self):
        self.publication = None

    def execute(self, sql, params=()):
        self.rows = []
        self.rowcount = 1
        if 'pg_try_advisory_lock' in sql:
            self.rows = [(True,)]
        elif 'SELECT job_id, csv_content' in sql:
            self.rows = [('synthetic-job', CSV)]
        elif 'SELECT csv_content' in sql:
            self.rows = []
        elif 'SELECT g.read_model' in sql:
            self.rows = [({'observed_prices': {}},)]
        elif 'LEFT JOIN hosted_snapshot_pointer' in sql:
            self.rows = [(self.generation, {'observed_prices': {}}, self.target_version)]
        elif 'FOR UPDATE' in sql and 'hosted_snapshot_pointer' in sql:
            if self.race == 'generation':
                self.generation = 'other-device-generation'
            if self.race == 'targets':
                self.target_version = '4'
            self.rows = [(self.generation,)]
        elif 'FOR SHARE' in sql and 'hosted_targets' in sql:
            self.rows = [(self.target_version,)]
        elif sql.startswith('INSERT INTO hosted_snapshot_generations'):
            self.publication = params[-1].adapted
        elif 'hosted_snapshot_pointer' in sql and sql.startswith(('UPDATE', 'INSERT')):
            if self.race == 'empty_pointer_insert':
                self.rowcount = 0
                return
            if self.race:
                raise AssertionError('Racing accepted state must not be overwritten')

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


@pytest.mark.parametrize('race', ['generation', 'targets'])
def test_import_rejects_concurrent_generation_or_target_edit_with_retryable_outcome(race):
    result = process_next(DatabaseTransport(race), SETTINGS)
    assert result.state == 'failed'
    assert result.diagnostics == ('publication_conflict_retry',)


def test_successful_import_retains_calculation_settings_hash_separately_from_targets_version():
    result = process_next(DatabaseTransport(), SETTINGS)
    assert result.state == 'completed'
    assert len(result.calculation_settings_version) == 64
    assert result.calculation_settings_version != result.rebalancing_targets_version
    assert result.rebalancing_targets_version == '3'


def test_first_publication_cannot_replace_another_writer_that_inserted_the_empty_pointer():
    result = process_next(DatabaseTransport('empty_pointer_insert', empty=True), SETTINGS)
    assert result.state == 'failed'
    assert result.diagnostics == ('publication_conflict_retry',)


def test_first_publication_is_supported_when_no_previous_snapshot_exists():
    result = process_next(DatabaseTransport(empty=True), SETTINGS)
    assert result.state == 'completed'
