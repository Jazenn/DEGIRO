from backend.engine.calculation import calculate_portfolio, ObservedPrice
from backend.ingestion.account_parser import parse_account_csv


def disposal_model(cost_complete=True):
    frame = parse_account_csv('Date,Time,Product,ISIN,Description,Amount,,Order Id\n'
        '02-01-2026,09:00,,,Deposit,EUR,100,\n'
        '03-01-2026,09:00,Coin,A,Buy 0.3 @ 100 EUR,EUR,-30,b1\n'
        '04-01-2026,09:00,Coin,A,Buy 0.3 @ 200 EUR,EUR,-60,b2\n'
        '05-01-2026,09:00,Coin,A,Sell 0.6 @ 200 EUR,EUR,120,s1\n'
        '05-01-2026,09:01,Coin,A,Transaction fee,EUR,-3,s1\n')
    settings = {'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic'},
        'cost_history': {'verified': cost_complete, 'evidence': 'synthetic'},
        'opening_baseline': {'at': '2026-01-01T00:00:00Z', 'cash_eur': '0', 'equity_eur': '0', 'verified': True, 'evidence': 'synthetic'},
        'asset_evidence': {'A': {'symbol': 'BTC-EUR', 'kind': 'Cryptocurrency', 'verified': True, 'evidence': 'synthetic'}}}
    return frame, calculate_portfolio(frame, observed_prices={'BTC-EUR': ObservedPrice('200', '2026-01-10T00:00:00Z', 'synthetic')},
        settings=settings, ledger_version='ledger-sale', settings_version='financial-sale', cutoff='2026-01-11T00:00:00Z').to_read_model()


def test_canonical_actual_disposal_retains_fill_identity_actual_fees_and_nonuniform_fifo_cost():
    frame, model = disposal_model()
    row = model['ledger']['disposals'][0]
    assert row['execution_id'] == frame.loc[frame.type == 'SELL', 'row_hash'].iloc[0]
    assert row['order_id'] == 's1'
    assert row['quantity'] == '0.6'
    assert row['gross_proceeds_eur'] == '120'
    assert row['fees_eur'] == '3'
    assert row['disposed_cost_eur'] == '90'
    assert row['realized_gain_eur'] == '27'
    assert row['cost_breakpoints'] == [{'quantity': '0', 'cost_eur': '0'}, {'quantity': '0.3', 'cost_eur': '30'}, {'quantity': '0.6', 'cost_eur': '90'}]
    assert row['executed_at'] == '2026-01-05T09:00:00+00:00'
    assert row['ledger_version'] == 'ledger-sale'
    assert row['financial_settings_version'] == 'financial-sale'
