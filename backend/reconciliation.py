"""Read-only comparison against privately reviewed source totals at matching cutoffs.

This checks evidence supplied by the owner; it does not independently prove that
source records are complete or authorize publication/cutover.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
import argparse
import json

TOTALS = ('cash_balance_eur', 'market_value_eur', 'equity_eur',
          'net_external_contributions_eur', 'net_gain_eur', 'attributed_gain_eur',
          'gross_income_eur', 'withholding_eur', 'net_income_eur', 'portfolio_costs_eur')
POSITION_AMOUNTS = ('quantity', 'retained_cost_eur', 'market_value_eur',
                    'held_gain_eur', 'realized_gain_eur')


def reconcile_snapshot(model, reference):
    """Compare canonical Snapshot read model to a source-reviewed ledger contract.

    All numeric evidence must be decimal strings; no float or tolerance hides
    financial differences. The returned report contains PRIVATE values.
    """
    checks = []

    def check(field, actual, expected, numeric=False):
        state = 'matched' if actual == expected else 'mismatch'
        if actual is None or expected is None:
            state = 'unavailable'
        elif numeric:
            try:
                if not isinstance(actual, str) or not isinstance(expected, str):
                    raise ValueError('Decimal strings required')
                a, e = Decimal(actual), Decimal(expected)
                if not a.is_finite() or not e.is_finite():
                    raise ValueError('Finite values required')
                state = 'matched' if a == e else 'mismatch'
            except (ValueError, InvalidOperation):
                state = 'unavailable'
        checks.append(dict(field=field, actual=actual, expected=expected, state=state))

    check('reference.schema_version', reference.get('schema_version'), 'private-reconciliation-v1')
    evidence = reference.get('source_evidence')
    check('reference.source_evidence', isinstance(evidence, str) and bool(evidence.strip()), True)
    for name in ('cutoff', 'ledger_cutoff'):
        check(name, model.get(name), reference.get(name))
        for side, value in (('snapshot', model.get(name)), ('reference', reference.get(name))):
            try:
                at = datetime.fromisoformat(value.replace('Z', '+00:00'))
                valid = 'T' in value and at.utcoffset() is not None
            except (AttributeError, TypeError, ValueError):
                valid = False
            check(f'{side}.{name}.verified_timestamp', valid, True)
    ledger, expected = model.get('ledger', {}), reference.get('ledger', {})
    for field in TOTALS:
        check('ledger.' + field, ledger.get(field), expected.get(field), numeric=True)
    for collection, identity, fields in (
        ('positions', 'broker_asset_id', POSITION_AMOUNTS),
        ('charges', 'transaction_id', ('date', 'category', 'amount_eur', 'allocation')),
    ):
        actual_rows, expected_rows = ledger.get(collection), expected.get(collection)
        if not isinstance(actual_rows, list) or not isinstance(expected_rows, list):
            check('ledger.' + collection, None, 'complete records required')
            continue
        def index(rows):
            if any(not isinstance(r, dict) or not isinstance(r.get(identity), str)
                   or not r[identity] for r in rows):
                return None
            result = {r[identity]: r for r in rows}
            return result if len(result) == len(rows) else None
        actual_index, expected_index = index(actual_rows), index(expected_rows)
        if actual_index is None or expected_index is None:
            check('ledger.' + collection, None, 'unique complete identities required')
            continue
        check('ledger.' + collection + '.identities', sorted(actual_index), sorted(expected_index))
        for key in sorted(actual_index.keys() & expected_index.keys()):
            for field in fields:
                check(f'ledger.{collection}.{key}.{field}', actual_index[key].get(field),
                      expected_index[key].get(field),
                      numeric=field in POSITION_AMOUNTS or field == 'amount_eur')
    state = 'passed' if all(c['state'] == 'matched' for c in checks) else (
        'mismatch' if any(c['state'] == 'mismatch' for c in checks) else 'unavailable')
    return dict(schema_version='private-reconciliation-report-v1', state=state, checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('reference', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    try:
        # Private records must live outside both this checkout and any enclosing
        # repository (including the parent repository of an isolated worktree).
        roots = [p for p in Path(__file__).resolve().parents if (p / '.git').exists()]
        for path in (args.snapshot, args.reference, args.report):
            if any(path.resolve().is_relative_to(root) for root in roots):
                raise ValueError('Private files require a directory outside the repository')
        model = json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
        reference = json.loads(args.reference.read_text(encoding='utf-8-sig'))
        report = reconcile_snapshot(model, reference)
        # Exclusive creation preserves earlier evidence, including failed checks.
        with args.report.open('x', encoding='utf-8') as destination:
            json.dump(report, destination, indent=2)
            destination.write('\n')
    except (OSError, ValueError, TypeError, AttributeError):
        print('Reconciliation could not run. Check private inputs and use a new report path.')
        return 2
    print('Private reconciliation report written; result: ' + report['state'] + '.')
    return 0 if report['state'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
