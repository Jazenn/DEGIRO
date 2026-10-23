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

@pytest.mark.parametrize('account_first',[False,True])
def test_inline_autofx_and_account_posting_are_one_economic_charge(account_first):
    from backend.engine.calculation import ObservedPrice
    transactions=b'Date,Time,Product,ISIN,Quantity,Price,Value EUR,AutoFX fee,Order Id\n03-01-2026,09:00,Fund,A,1,1000,-1000,-2,o\n'
    account=(b'Date,Time,Product,ISIN,Description,Amount,,Order Id\n02-01-2026,09:00,,,Deposit,EUR,1002,\n'
             b'03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o\n03-01-2026,09:01,Fund,A,AutoFX fee,EUR,-2,o\n')
    sources=[account,transactions] if account_first else [transactions,account]
    settings={**SETTINGS,'asset_evidence':{'A':{'verified':True,'evidence':'synthetic','symbol':'ETF','kind':'ETF'}}}
    model=stage_generation(sources,settings=settings,quotes={'ETF':ObservedPrice('1100','2026-01-10T00:00:00Z','synthetic')},cutoff='2026-01-11T00:00:00Z')
    ledger=model['ledger']
    assert ledger['cash_balance_eur']=='0'
    assert ledger['positions'][0]['retained_cost_eur']=='1002'
    assert ledger['net_gain_eur']=='98'
    assert len(ledger['charges'])==1 and ledger['charges'][0]['amount_eur']=='2'

def test_autofx_corroboration_keeps_equal_broker_commission_and_rejects_uncertain_overlap():
    from backend.engine.calculation import ObservedPrice
    transactions=b'Date,Time,Product,ISIN,Quantity,Price,Value EUR,Fee,AutoFX fee,Order Id\n03-01-2026,09:00,Fund,A,1,1000,-1000,-2,-2,o\n'
    account=(b'Date,Time,Product,ISIN,Description,Amount,,Order Id\n02-01-2026,09:00,,,Deposit,EUR,1004,\n'
             b'03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o\n'
             b'03-01-2026,09:00,Fund,A,Transaction fee,EUR,-2,o\n03-01-2026,09:01,Fund,A,AutoFX fee,EUR,-2,o\n')
    settings={**SETTINGS,'asset_evidence':{'A':{'verified':True,'evidence':'synthetic','symbol':'ETF','kind':'ETF'}}}
    args=dict(settings=settings,quotes={'ETF':ObservedPrice('1100','2026-01-10T00:00:00Z','synthetic')},cutoff='2026-01-11T00:00:00Z')
    ledger=stage_generation([transactions,account],**args)['ledger']
    assert (ledger['cash_balance_eur'],ledger['positions'][0]['retained_cost_eur'],ledger['net_gain_eur'])==('0','1004','96')
    assert sorted((charge['category'],charge['amount_eur']) for charge in ledger['charges'])==[('recorded_fee','2'),('recorded_fx','2')]
    with pytest.raises(ValueError,match='ambiguous_autofx_fee_overlap_requires_review'):
        stage_generation([transactions,account.replace(b'AutoFX fee,EUR,-2,o',b'AutoFX fee,EUR,-3,o')],**args)

def test_ledger_version_changes_when_source_interpretation_schema_changes():
    result=stage_generation([CSV],settings=SETTINGS,quotes={},cutoff='2026-01-10T00:00:00Z')
    # Prior unversioned implementation's independently recorded digest for CSV.
    assert result['ledger_version']!='ab83e4ebde6ba1e92a03d44877d726e2429288426993e01037a528f560904abb'
    assert result['ledger_version']==stage_generation([CSV],settings=SETTINGS,quotes={},cutoff='2026-01-10T00:00:00Z')['ledger_version']
