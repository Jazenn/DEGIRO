from backend.engine.history import calculate_history
from backend.engine.calculation import ObservedPrice
from backend.ingestion.account_parser import parse_account_csv


def scenario():
    transactions = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n'
        '01-01-2026,09:00,,,Deposit,EUR,1000,\n'
        '01-01-2026,10:00,Fund,A,Buy 2 @ 100 EUR,EUR,-200,b\n'
        '01-01-2026,10:01,Fund,A,Transaction fee,EUR,-2,b\n'
        '02-01-2026,09:00,Fund,A,Dividend,EUR,4,\n'
        '02-01-2026,09:01,Fund,A,Dividend withholding,EUR,-1,\n'
        '02-01-2026,09:02,,,Account fee,EUR,-2,\n'
        '03-01-2026,10:00,Fund,A,Sell 1 @ 120 EUR,EUR,120,s1\n'
        '03-01-2026,10:01,Fund,A,Transaction fee,EUR,-1,s1\n'
        '04-01-2026,10:00,Fund,A,Sell 1 @ 130 EUR,EUR,130,s2\n'
        '04-01-2026,10:01,Fund,A,Transaction fee,EUR,-1,s2\n')
    settings = {'cost_history': {'verified': True, 'evidence': 'synthetic complete'},
        'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic'},
        'opening_baseline': {'verified': True, 'evidence': 'synthetic first funding', 'at': '2026-01-01T00:00:00Z', 'cash_eur': '0', 'equity_eur': '0'},
        'asset_evidence': {'A': {'verified': True, 'evidence': 'synthetic', 'symbol': 'ETF', 'kind': 'ETF'}}}
    daily = {f'2026-01-0{day}T00:00:00Z': {'ETF': ObservedPrice(price, f'2026-01-0{day-1}T16:30:00Z', 'synthetic exchange close')} for day, price in [(2, '110'), (3, '120'), (4, '125'), (5, '130')]}
    evidence = {'ETF': {'corporate_actions_reconciled': True, 'official_close_verified': True, 'evidence': 'synthetic no splits, distributions reconciled'}}
    return transactions, settings, daily, evidence


def history(**changes):
    transactions, settings, daily, evidence = scenario()
    args = dict(transactions=transactions, settings=settings, daily_prices=daily, asset_coverage=evidence,
                ledger_version='ledger-1', settings_version='settings-1', now='2026-01-05T12:00:00Z')
    args.update(changes)
    return calculate_history(**args)


def test_observed_chart_and_attribution_share_cutoffs_and_retain_closed_asset_gain():
    result = history()
    period = result['periods']['ALL']
    assert period['state'] == 'ready'
    assert (period['start'], period['end']) == ('2026-01-01T00:00:00Z', '2026-01-05T00:00:00Z')
    assert [point['equity_eur'] for point in period['points']] == ['0', '1018', '1039', '1043', '1047']
    assert period['attribution'] == {'retained_gain_change_eur': '0', 'realized_gain_change_eur': '46',
        'net_income_eur': '3', 'portfolio_costs_eur': '2', 'net_external_flows_eur': '1000', 'net_gain_eur': '47'}
    assert period['assets'][0]['symbol'] == 'ETF'
    assert period['assets'][0]['realized_gain_change_eur'] == '46'
    assert result['cutoff'] == '2026-01-05T00:00:00Z'

def test_calendar_months_clamp_and_missing_opening_is_explicit():
    from backend.engine.history import calendar_months, instant
    assert calendar_months(instant('2024-03-31T00:00:00Z'), 1).isoformat() == '2024-02-29T00:00:00+00:00'
    assert calendar_months(instant('2024-02-29T00:00:00Z'), 12).isoformat() == '2023-02-28T00:00:00+00:00'
    result = history()
    assert set(result['periods']) == {'ALL', 'YTD', '1Y', '3M', '1M', '1W'}
    assert result['periods']['1Y']['shorter_coverage'] is True
    assert result['periods']['1Y']['requested_start'] == '2025-01-05T00:00:00Z'


def test_unexpected_gap_withholds_period_instead_of_bridging_or_zero():
    _, _, daily, _ = scenario()
    daily.pop('2026-01-03T00:00:00Z')
    period = history(daily_prices=daily)['periods']['ALL']
    assert period['state'] == 'unavailable'
    assert period['points'][2]['equity_eur'] is None
    assert 'attribution' not in period
    assert period['estimated_return']['state'] == 'unavailable'
    assert period['estimated_return']['percent'] is None


def test_market_closure_preserves_original_price_date_but_requires_calendar_evidence():
    _, _, daily, _ = scenario()
    daily['2026-01-03T00:00:00Z'] = daily['2026-01-02T00:00:00Z']
    period = history(daily_prices=daily)['periods']['ALL']
    assert period['state'] == 'unavailable'
    assert 'unexpected_price_gap:ETF' in period['diagnostics']
    result = history(daily_prices=daily, market_closures={'2026-01-03T00:00:00Z': {'ETF': 'synthetic exchange calendar closed'}})
    period = result['periods']['ALL']
    assert period['state'] == 'ready'
    assert period['points'][2]['observed_prices']['ETF']['observed_at'] == '2026-01-01T16:30:00Z'


def test_unresolved_corporate_actions_and_non_eur_cash_without_dated_fx_withhold_history():
    result = history(asset_coverage={})
    assert result['periods']['ALL']['state'] == 'unavailable'
    assert 'corporate_actions_unresolved:ETF' in result['periods']['ALL']['diagnostics']
    transactions, _, _, _ = scenario()
    transactions.loc[transactions['type'] == 'DIVIDEND', 'amount_currency'] = 'USD'
    assert history(transactions=transactions)['periods']['ALL']['state'] == 'unavailable'

def test_crypto_completed_day_requires_its_exact_midnight_observation():
    _, settings, daily, _ = scenario()
    settings['asset_evidence']['A']['kind'] = 'Cryptocurrency'
    result = history(settings=settings, daily_prices=daily)
    assert result['periods']['ALL']['state'] == 'unavailable'
    assert 'crypto_daily_close_missing:ETF' in result['periods']['ALL']['diagnostics']

def test_background_provider_adapter_discards_live_tail_and_keeps_exact_midnight_provenance(monkeypatch):
    import io
    import json
    from backend.providers.history import fetch_history_input
    payload = {'prices': [[1767312000000, '110.1234567890123456789'], [1767355200000, '999'], [1767398400000, '120']]}
    monkeypatch.setattr('urllib.request.urlopen', lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    result = fetch_history_input({'history_sources': {'BTC': {'provider': 'coingecko', 'coin_id': 'bitcoin', 'verified': True, 'evidence': 'synthetic mapping'}}}, now='2026-01-03T12:00:00Z')
    assert set(result['daily_prices']) == {'2026-01-02T00:00:00Z', '2026-01-03T00:00:00Z'}
    quote = result['daily_prices']['2026-01-02T00:00:00Z']['BTC']
    assert quote['price_eur'] == '110.1234567890123456789'
    assert quote['currency'] == 'EUR'
    assert quote['provider'] == 'CoinGecko Demo market_chart EUR daily'
    assert quote['observed_at'] == '2026-01-02T00:00:00Z'

def test_persisted_history_keeps_scalar_series_provenance_and_attribution_without_daily_ledgers():
    import json
    result=history()
    for period in result['periods'].values():
        assert all('ledger' not in point for point in period['points'])
    period=result['periods']['ALL']
    assert [point['equity_eur'] for point in period['points']]==['0','1018','1039','1043','1047']
    assert period['attribution']['net_gain_eur']=='47'
    assert period['points'][1]['observed_prices']['ETF']['provider']=='synthetic exchange close'
    assert period['estimated_return']['state']=='ready'
    json.dumps(result,allow_nan=False)
