import json
import subprocess
import sys
from copy import deepcopy

from backend.hosted_snapshot import synthetic_read_model
from backend.reconciliation import reconcile_snapshot


def reference(model):
    return {
        'schema_version': 'private-reconciliation-v1',
        'source_evidence': 'Synthetic independently checked purchase 1000 + fee 5; observed value 1100.',
        'cutoff': model['cutoff'], 'ledger_cutoff': model['ledger_cutoff'],
        'ledger': deepcopy(model['ledger']),
    }


def test_matched_cutoff_reconciliation_accepts_fee_inclusive_worked_example():
    model = synthetic_read_model()
    expected = reference(model)
    # Independent spec literals, not values calculated by the comparator.
    expected['ledger'].update(cash_balance_eur='0', market_value_eur='1100',
                             equity_eur='1100', net_external_contributions_eur='1005',
                             net_gain_eur='95', attributed_gain_eur='95')
    report = reconcile_snapshot(model, expected)
    assert report['state'] == 'passed'
    assert report['checks']


def test_reconciliation_never_hides_missing_extra_or_changed_holdings_and_costs():
    model = synthetic_read_model()
    expected = reference(model)
    model['ledger']['positions'][0]['retained_cost_eur'] = '1000'
    model['ledger']['charges'] = []
    report = reconcile_snapshot(model, expected)
    assert report['state'] == 'mismatch'
    assert any(c['field'].endswith('retained_cost_eur') and c['state'] == 'mismatch' for c in report['checks'])
    assert any('charges' in c['field'] and c['state'] == 'mismatch' for c in report['checks'])


def test_missing_gain_and_wrong_cutoff_cannot_pass_even_when_both_sides_agree():
    model = synthetic_read_model()
    expected = reference(model)
    model['ledger']['net_gain_eur'] = expected['ledger']['net_gain_eur'] = None
    assert reconcile_snapshot(model, expected)['state'] == 'unavailable'
    expected['cutoff'] = '2026-01-12T00:00:00Z'
    assert reconcile_snapshot(model, expected)['state'] == 'mismatch'


def test_private_cli_writes_report_without_printing_financial_records(tmp_path):
    model = synthetic_read_model()
    snapshot, source, report = (tmp_path / name for name in ('snapshot.json', 'source.json', 'report.json'))
    snapshot.write_text(json.dumps(model), encoding='utf-8')
    source.write_text(json.dumps(reference(model)), encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'backend.reconciliation',
                             str(snapshot), str(source), '--report', str(report)],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(report.read_text())['state'] == 'passed'
    assert '1005' not in result.stdout + result.stderr
    assert 'SYNTHETIC' not in result.stdout + result.stderr
    # Reports must never silently replace previously recorded release evidence.
    retry = subprocess.run([sys.executable, '-m', 'backend.reconciliation',
                            str(snapshot), str(source), '--report', str(report)],
                           capture_output=True, text=True)
    assert retry.returncode == 2


def test_reconciliation_requires_valid_cutoffs_and_source_evidence():
    model = synthetic_read_model()
    expected = reference(model)
    model['cutoff'] = expected['cutoff'] = 'not-a-date'
    expected['source_evidence'] = '  '
    assert reconcile_snapshot(model, expected)['state'] != 'passed'


def test_duplicate_identities_and_nonfinite_amounts_are_unavailable():
    model = synthetic_read_model()
    expected = reference(model)
    model['ledger']['cash_balance_eur'] = expected['ledger']['cash_balance_eur'] = 'NaN'
    assert reconcile_snapshot(model, expected)['state'] == 'unavailable'
    model = synthetic_read_model()
    expected = reference(model)
    model['ledger']['positions'].append(deepcopy(model['ledger']['positions'][0]))
    assert reconcile_snapshot(model, expected)['state'] == 'unavailable'


def test_unexpected_holdings_are_mismatches_and_missing_costs_are_unavailable():
    model = synthetic_read_model()
    expected = reference(model)
    expected['ledger']['positions'] = []
    assert reconcile_snapshot(model, expected)['state'] == 'mismatch'
    expected = reference(model)
    model['ledger']['positions'][0]['retained_cost_eur'] = None
    assert reconcile_snapshot(model, expected)['state'] == 'unavailable'


def test_cli_refuses_any_report_path_inside_repository(tmp_path):
    from pathlib import Path
    model = synthetic_read_model()
    snapshot, source = (tmp_path / name for name in ('snapshot.json', 'source.json'))
    snapshot.write_text(json.dumps(model), encoding='utf-8')
    source.write_text(json.dumps(reference(model)), encoding='utf-8')
    report = Path('private-reconciliation-must-not-write.json')
    result = subprocess.run([sys.executable, '-m', 'backend.reconciliation', str(snapshot),
                             str(source), '--report', str(report)], capture_output=True, text=True)
    assert result.returncode == 2
    assert not report.exists()
