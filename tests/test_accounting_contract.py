from decimal import Decimal as D
from backend.ingestion.account_parser import parse_account_csv
from backend.engine.calculation import calculate_portfolio, ObservedPrice


def report(rows, prices=None, **overrides):
    text = 'Date,Time,Product,ISIN,Description,Amount,,Order Id\n' + '\n'.join(rows)
    settings = {'cost_history': {'verified': True, 'evidence': 'complete synthetic history'}, 'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic fixture'},
                'opening_baseline': {'verified': True, 'evidence': 'synthetic first funding', 'at': '2026-01-01T00:00:00Z', 'cash_eur': '0', 'equity_eur': '0'},
                'asset_evidence': {'A': {'verified': True, 'evidence': 'synthetic asset', 'symbol': 'ETF', 'kind': 'ETF'}}}
    settings.update(overrides)
    return calculate_portfolio(parse_account_csv(text), observed_prices={s: ObservedPrice(p, '2026-01-10T00:00:00Z', 'synthetic') for s,p in (prices or {'ETF': '1100'}).items()}, settings=settings, ledger_version='test', settings_version='test', cutoff='2026-01-11T00:00:00Z').ledger


def test_acquisition_fee_is_in_retained_cost_and_equity_bridge():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1005,',
                     '03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o',
                     '03-01-2026,09:01,Fund,A,Transaction fee,EUR,-5,o'])
    assert ledger.positions[0].retained_cost_eur == D('1005')
    assert ledger.positions[0].held_gain_eur == D('95')
    assert ledger.net_gain_eur == D('95')
    assert ledger.attributed_gain_eur == D('95')


def test_growth_income_and_portfolio_cost_reconcile_once():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1000,',
                     '03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o',
                     '04-01-2026,09:00,Fund,A,Dividend,EUR,25,',
                     '04-01-2026,09:01,Fund,A,Dividend withholding,EUR,-5,',
                     '05-01-2026,09:00,,,Account fee,EUR,-5,'])
    assert (ledger.net_gain_eur, ledger.attributed_gain_eur, ledger.net_income_eur) == (D('115'), D('115'), D('20'))
    assert ledger.charges[0].date == '2026-01-05'


def test_sale_reinvestment_retains_realized_gain_and_remaining_lots():
    evidence = {'A': {'verified': True, 'evidence': 'synthetic', 'symbol': 'BTC', 'kind': 'Cryptocurrency'},
                'B': {'verified': True, 'evidence': 'synthetic', 'symbol': 'ETF', 'kind': 'ETF'}}
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1000,',
                     '03-01-2026,09:00,Coin,A,Buy 1 @ 1000 EUR,EUR,-1000,a',
                     '04-01-2026,09:00,Coin,A,Sell 0.5 @ 1500 EUR,EUR,750,b',
                     '05-01-2026,09:00,Fund,B,Buy 1 @ 750 EUR,EUR,-750,c'],
                    {'BTC': '1200', 'ETF': '750'}, asset_evidence=evidence)
    assert (ledger.equity_eur, ledger.net_gain_eur, ledger.attributed_gain_eur) == (D('1350'), D('350'), D('350'))
    assert (ledger.positions[0].realized_gain_eur, ledger.positions[0].held_gain_eur) == (D('250'), D('100'))


def test_transactions_inline_fx_cost_is_posted_once_and_allocated_to_cost():
    from backend.ingestion.transaction_parser import parse_transactions_csv
    frame = parse_transactions_csv('Date,Time,Product,ISIN,Quantity,Price,Value EUR,Fee,AutoFX fee,Order Id\n03-01-2026,09:00,Fund,A,1,1000,-1000,-5,-2,o\n')
    result = calculate_portfolio(frame, observed_prices={'ETF': ObservedPrice(1100, '2026-01-10T00:00:00Z', 'synthetic')},
        settings={'asset_evidence': {'A': {'verified': True, 'evidence': 'fixture', 'symbol': 'ETF', 'kind': 'ETF'}}},
        ledger_version='test', settings_version='test', cutoff='2026-01-11T00:00:00Z').ledger
    assert result.positions[0].retained_cost_eur == D('1007')
    assert sum((c.amount_eur for c in result.charges), D(0)) == D('7')


def test_missing_price_and_opening_evidence_withhold_results_without_cost_valuation():
    ledger = report(['03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o'],
                    {'OTHER': '1100'}, opening_baseline={})
    assert ledger.positions[0].market_value_eur is None
    assert ledger.equity_eur is None
    assert ledger.net_gain_eur is None
    assert 'verified_opening_baseline_required' in ledger.diagnostics


def test_fractional_multiple_fifo_lots_and_closed_position_keep_fees_and_results():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1005,',
                     '03-01-2026,09:00,Fund,A,Buy 0.25 @ 1000 EUR,EUR,-250,a',
                     '03-01-2026,09:01,Fund,A,Transaction fee,EUR,-1,a',
                     '04-01-2026,09:00,Fund,A,Buy 0.75 @ 1000 EUR,EUR,-750,b',
                     '04-01-2026,09:01,Fund,A,Transaction fee,EUR,-4,b',
                     '05-01-2026,09:00,Fund,A,Sell 1 @ 1100 EUR,EUR,1100,c',
                     '05-01-2026,09:01,Fund,A,Transaction fee,EUR,-5,c'])
    assert ledger.positions[0].quantity == D('0')
    assert ledger.positions[0].realized_gain_eur == D('90')
    assert ledger.net_gain_eur == D('90')


def test_read_model_serializes_exact_decimals_and_versions_for_new_consumers():
    import json
    frame = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o\n')
    result = calculate_portfolio(frame, observed_prices={}, settings={}, ledger_version='ledger-9', settings_version='settings-3', cutoff='2026-01-11T00:00:00Z')
    payload = result.to_read_model()
    assert payload['ledger_version'] == 'ledger-9'
    assert payload['ledger']['positions'][0]['retained_cost_eur'] == '1000'
    assert payload['ledger']['positions'][0]['market_value_eur'] is None
    json.dumps(payload, allow_nan=False)


def test_english_grouping_and_fractional_source_precision_are_preserved():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,"1,234.56",',
                     '03-01-2026,09:00,Fund,A,Buy 0.1234567890123456789 @ 10000 EUR,EUR,"-1,234.56",o'], {'ETF': '10000'})
    assert ledger.positions[0].quantity == D('0.1234567890123456789')
    assert ledger.positions[0].retained_cost_eur == D('1234.56')
    assert ledger.positions[0].market_value_eur == D('1234.5678901234567890000')


def test_verified_source_timezone_includes_local_trade_before_utc_cutoff():
    frame = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n11-01-2026,00:30,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o\n')
    result = calculate_portfolio(frame, observed_prices={}, settings={'source_timezone': {'name': 'Europe/Amsterdam', 'verified': True, 'evidence': 'synthetic'}}, ledger_version='v', settings_version='s', cutoff='2026-01-11T00:00:00Z')
    assert result.ledger.positions[0].quantity == D('1')


def test_ambiguous_verified_local_time_cannot_publish_a_generation():
    import pytest
    frame = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n25-10-2026,02:30,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o\n')
    with pytest.raises(Exception, match='[Aa]mbiguous|Cannot infer dst'):
        calculate_portfolio(frame, observed_prices={}, settings={'source_timezone': {'name': 'Europe/Amsterdam', 'verified': True, 'evidence': 'synthetic'}}, ledger_version='v', settings_version='s', cutoff='2026-10-26T00:00:00Z')


def test_verified_dated_fx_converts_actual_cash_and_lot_cost():
    frame = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n03-01-2026,09:00,Fund,A,Buy 1 @ 1000 USD,USD,-1000,o\n')
    row_id = frame.iloc[0]['row_hash']
    result = calculate_portfolio(frame, observed_prices={'ETF': ObservedPrice(1000, '2026-01-10T00:00:00Z', 'synthetic')},
        settings={'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic'}, 'cost_history': {'verified': True, 'evidence': 'complete synthetic history'}, 'fx_evidence': {row_id: {'verified': True, 'date': '2026-01-03', 'currency': 'USD', 'eur_per_unit': '0.9', 'provider': 'synthetic'}},
                  'asset_evidence': {'A': {'verified': True, 'evidence': 'synthetic', 'symbol': 'ETF', 'kind': 'ETF'}}},
        ledger_version='v', settings_version='s', cutoff='2026-01-11T00:00:00Z')
    assert result.ledger.positions[0].retained_cost_eur == D('900')
    assert result.ledger.positions[0].held_gain_eur == D('100')


def test_unverified_cost_history_withholds_gain_but_preserves_observed_market_value():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1000,',
                     '03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o'], cost_history={})
    assert ledger.positions[0].market_value_eur == D('1100')
    assert ledger.positions[0].held_gain_eur is None
    assert ledger.net_gain_eur is None
    assert 'cost_history_completeness_unverified' in ledger.diagnostics


def test_mixed_export_overlap_does_not_deduct_inline_and_separate_fee_twice():
    from backend.ingestion.service import TransactionIngestionService
    import pandas as pd
    service = TransactionIngestionService()
    account = service.ingest_csv(b'Date,Time,Product,ISIN,Description,Amount,,Order Id\n03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o\n03-01-2026,09:00,Fund,A,Transaction fee,EUR,-5,o\n')
    trades = service.ingest_csv(b'Date,Time,Product,ISIN,Quantity,Price,Value EUR,Fee,Order Id\n03-01-2026,09:00,Fund,A,1,1000,-1000,-5,o\n')
    assert account.accepted and trades.accepted
    assert trades.new_rows == 0
    result = calculate_portfolio(pd.concat([account.transactions, trades.transactions]), observed_prices={}, settings={}, ledger_version='v', settings_version='s', cutoff='2026-01-11T00:00:00Z')
    assert result.ledger.positions[0].retained_cost_eur == D('1005')
    assert len(result.ledger.charges) == 1


def test_unverified_source_timezone_withholds_every_cutoff_dependent_gain():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1000,',
                     '03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o',
                     '04-01-2026,09:00,Fund,A,Sell 0.5 @ 1100 EUR,EUR,550,s'], source_timezone={})
    position = ledger.positions[0]
    assert position.retained_cost_eur == D('500')
    assert (position.held_gain_eur, position.realized_gain_eur,
            ledger.attributed_gain_eur, ledger.net_gain_eur) == (None, None, None, None)


def test_unverified_opening_baseline_withholds_total_attribution_but_keeps_known_lot_gain():
    ledger = report(['03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o'], opening_baseline={})
    assert ledger.positions[0].held_gain_eur == D('100')
    assert ledger.net_gain_eur is None
    assert ledger.attributed_gain_eur is None


def test_empty_ledger_verified_cash_baseline_needs_no_source_timezone():
    import pandas as pd
    result = calculate_portfolio(pd.DataFrame(), observed_prices={},
        settings={'opening_baseline': {'at': '2026-01-01T00:00:00Z', 'cash_eur': '100', 'equity_eur': '100', 'verified': True, 'evidence': 'synthetic'},
                  'cost_history': {'verified': True, 'evidence': 'empty synthetic ledger'}},
        ledger_version='v', settings_version='s', cutoff='2026-01-11T00:00:00Z').ledger
    assert (result.net_gain_eur, result.attributed_gain_eur) == (D('0'), D('0'))
    assert not any('timezone' in diagnostic for diagnostic in result.diagnostics)


def test_sale_beyond_known_inventory_rejects_generation():
    import pytest
    with pytest.raises(ValueError, match='sale_quantity_exceeds_known_inventory'):
        report(['02-01-2026,09:00,,,Deposit,EUR,1000,',
                '03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,-1000,o',
                '04-01-2026,09:00,Fund,A,Sell 2 @ 1100 EUR,EUR,2200,s'])


def test_missing_purchase_posting_withholds_dependent_equity_and_total_gain():
    ledger = report(['02-01-2026,09:00,,,Deposit,EUR,1000,',
                     '03-01-2026,09:00,Fund,A,Buy 1 @ 1000 EUR,EUR,0,o'])
    assert ledger.positions[0].market_value_eur == D('1100')
    assert ledger.positions[0].retained_cost_eur is None
    assert (ledger.cash_balance_eur, ledger.equity_eur,
            ledger.net_gain_eur, ledger.attributed_gain_eur) == (None, None, None, None)
