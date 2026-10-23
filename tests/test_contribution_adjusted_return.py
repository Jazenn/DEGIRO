from decimal import Decimal
from backend.engine.history import calculate_history
from backend.ingestion.account_parser import parse_account_csv


def cash_history(rows, *, baseline='1000', now='2026-01-02T12:00:00Z', timezone=None, start='2026-01-01T00:00:00Z'):
    frame = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n' + '\n'.join(rows))
    return calculate_history(frame, settings={
        'cost_history': {'verified': True, 'evidence': 'synthetic complete'},
        'source_timezone': timezone or {'name': 'UTC', 'verified': True, 'evidence': 'synthetic'},
        'opening_baseline': {'verified': True, 'evidence': 'synthetic cash only', 'at': start, 'cash_eur': baseline, 'equity_eur': baseline}},
        daily_prices={'2026-01-02T00:00:00Z': {}}, asset_coverage={}, ledger_version='synthetic', settings_version='synthetic', now=now)


def test_endpoint_deposit_has_zero_weight_and_preserves_ten_percent_gain():
    result = cash_history(['01-01-2026,12:00,,,Dividend,EUR,100,', '02-01-2026,00:00,,,Deposit,EUR,500,'])
    period = result['periods']['ALL']
    assert period['attribution']['net_gain_eur'] == '100'
    estimate = period['estimated_return']
    assert estimate['state'] == 'ready'
    assert Decimal(estimate['percent']) == Decimal('10')
    assert estimate['daily'][0]['weighted_external_flows_eur'] == '0'
    assert estimate['daily'][0]['denominator_eur'] == '1000'
    assert estimate['cutoff'] == '2026-01-02T00:00:00Z'

def test_intraday_first_funding_then_growth_links_daily_estimates_geometrically():
    result = cash_history(['01-01-2026,12:00,,,Deposit,EUR,1000,', '02-01-2026,12:00,,,Dividend,EUR,100,', '03-01-2026,12:00,,,Dividend withholding,EUR,-110,'], baseline='0', now='2026-01-04T22:00:00Z')
    estimate = result['periods']['ALL']['estimated_return']
    assert estimate['state'] == 'ready'
    assert Decimal(estimate['percent']) == Decimal('-1')
    assert [Decimal(day['fraction']) for day in estimate['daily']] == [Decimal('0'), Decimal('0.1'), Decimal('-0.1')]
    assert estimate['daily'][0]['denominator_eur'] == '500.0'
    assert estimate['cutoff'] == '2026-01-04T00:00:00Z'


def test_full_withdrawal_followed_by_intraday_refunding_has_its_own_weighted_capital():
    result = cash_history(['02-01-2026,00:00,,,Withdrawal,EUR,-1000,', '02-01-2026,12:00,,,Deposit,EUR,500,', '02-01-2026,18:00,,,Dividend,EUR,50,'], now='2026-01-03T12:00:00Z')
    estimate = result['periods']['ALL']['estimated_return']
    assert estimate['state'] == 'ready'
    assert Decimal(estimate['percent']) == Decimal('20')
    assert estimate['daily'][1]['denominator_eur'] == '250.0'


def test_endpoint_first_funding_and_unfunded_gap_never_create_zero_returns():
    first = cash_history(['02-01-2026,00:00,,,Deposit,EUR,1000,'], baseline='0')['periods']['ALL']['estimated_return']
    assert first['state'] == 'unavailable'
    assert first['percent'] is None
    assert first['diagnostics'] == ['nonpositive_daily_dietz_denominator']
    gap = cash_history(['02-01-2026,00:00,,,Withdrawal,EUR,-1000,', '04-01-2026,12:00,,,Deposit,EUR,500,'], now='2026-01-05T12:00:00Z')['periods']['ALL']['estimated_return']
    assert gap['state'] == 'unavailable'
    assert gap['percent'] is None


def test_unverified_flow_timezone_and_missing_timing_withhold_estimate():
    result = cash_history(['01-01-2026,12:00,,,Deposit,EUR,500,'], timezone={'name': 'UTC', 'verified': False, 'evidence': ''})
    assert result['periods']['ALL']['estimated_return']['state'] == 'unavailable'
    result = cash_history(['01-01-2026,,,,Deposit,EUR,500,'])
    assert result['periods']['ALL']['estimated_return']['state'] == 'unavailable'


def test_dst_ambiguous_flow_time_withholds_daily_return_without_crashing_history():
    result = cash_history(['25-10-2026,02:30,,,Deposit,EUR,500,'], start='2026-10-24T00:00:00Z', now='2026-10-26T12:00:00Z', timezone={'name': 'Europe/Amsterdam', 'verified': True, 'evidence': 'synthetic broker convention'})
    estimate = result['periods']['ALL']['estimated_return']
    assert estimate['state'] == 'unavailable'
    assert estimate['percent'] is None


def test_midday_signed_flow_uses_half_interval_weight():
    estimate = cash_history(['01-01-2026,12:00,,,Deposit,EUR,500,', '01-01-2026,18:00,,,Dividend,EUR,125,'])['periods']['ALL']['estimated_return']
    assert Decimal(estimate['percent']) == Decimal('10')
    assert estimate['daily'][0]['weighted_external_flows_eur'] == '250.0'
    assert estimate['daily'][0]['denominator_eur'] == '1250.0'

def test_verified_broker_timezone_weights_against_utc_interval_not_local_clock():
    estimate = cash_history(['01-01-2026,13:00,,,Deposit,EUR,500,', '01-01-2026,19:00,,,Dividend,EUR,125,'], timezone={'name': 'Europe/Amsterdam', 'verified': True, 'evidence': 'synthetic broker convention'})['periods']['ALL']['estimated_return']
    assert Decimal(estimate['percent']) == Decimal('10')
    assert estimate['daily'][0]['weighted_external_flows_eur'] == '250.0'


def test_nonexistent_dst_flow_time_withholds_without_substituting_midnight():
    result = cash_history(['29-03-2026,02:30,,,Deposit,EUR,500,'], start='2026-03-28T00:00:00Z', now='2026-03-30T12:00:00Z', timezone={'name': 'Europe/Amsterdam', 'verified': True, 'evidence': 'synthetic broker convention'})
    assert result['periods']['ALL']['estimated_return']['state'] == 'unavailable'

def test_verified_zero_prefunding_prefix_establishes_explicit_supported_percentage_start():
    result = cash_history(['03-01-2026,00:00,,,Deposit,EUR,1000,', '03-01-2026,12:00,,,Dividend,EUR,100,'], baseline='0', now='2026-01-04T12:00:00Z')
    period = result['periods']['ALL']
    assert period['start'] == '2026-01-01T00:00:00Z'
    assert period['attribution']['net_gain_eur'] == '100'
    estimate = period['estimated_return']
    assert estimate['state'] == 'ready'
    assert Decimal(estimate['percent']) == Decimal('10')
    assert estimate['start'] == '2026-01-03T00:00:00Z'
    assert estimate['opening_coverage'] == 'first_funded_baseline'
    assert estimate['requested_start'] == '2026-01-01T00:00:00Z'
    assert estimate['excluded_prefunding_intervals'] == ['2026-01-02T00:00:00Z', '2026-01-03T00:00:00Z']
