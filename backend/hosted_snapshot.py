"""Explicit synthetic staging seed; never used as a browser fallback.

Generate is local-only. Seed requires an explicitly approved, empty staging DB.
No legacy tables or existing accepted generation are changed.
"""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from backend.engine.calculation import ObservedPrice, calculate_portfolio
from backend.ingestion.account_parser import parse_account_csv


def synthetic_read_model():
    transactions = parse_account_csv(
        'Date,Time,Product,ISIN,Description,Amount,,Order Id\n'
        '02-01-2026,09:00,,,Deposit,EUR,1005,\n'
        '03-01-2026,09:00,Synthetic Fund,SYNTHETIC-A,Buy 1 @ 1000 EUR,EUR,-1000,synthetic-order\n'
        '03-01-2026,09:01,Synthetic Fund,SYNTHETIC-A,Transaction fee,EUR,-5,synthetic-order\n')
    settings = {
        'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic fixture only'},
        'cost_history': {'verified': True, 'evidence': 'complete synthetic history only'},
        'opening_baseline': {'at': '2026-01-01T00:00:00Z', 'cash_eur': '0', 'equity_eur': '0',
                             'verified': True, 'evidence': 'synthetic initial funding only'},
        'asset_evidence': {'SYNTHETIC-A': {'symbol': 'SYNTHETIC', 'kind': 'ETF', 'verified': True,
                                         'evidence': 'invented synthetic Asset, not a broker mapping'}},
    }
    return calculate_portfolio(
        transactions, observed_prices={'SYNTHETIC': ObservedPrice(
            '1100', '2026-01-10T00:00:00Z', 'synthetic-only', retrieved_at='2026-01-10T00:01:00Z')},
        settings=settings, ledger_version='synthetic-ledger-1', settings_version='synthetic-settings-1',
        cutoff='2026-01-11T00:00:00Z').to_read_model()


def seed_synthetic():
    from backend.db.connection import get_db_connection
    from psycopg2.extras import Json
    if os.environ.get('HOSTED_STAGING_SEED_APPROVED') != 'synthetic-empty-database':
        raise ValueError('Explicit approved empty staging database confirmation required')
    # No config-file or legacy credential fallback: caller explicitly supplies the staging URL.
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise ValueError('Explicit staging DATABASE_URL required')
    model = synthetic_read_model()
    generation = 'synthetic-' + str(uuid4())
    with get_db_connection(url) as connection, connection.cursor() as cursor:
        cursor.execute('LOCK TABLE hosted_snapshot_generations, hosted_snapshot_pointer IN EXCLUSIVE MODE')
        cursor.execute('SELECT EXISTS(SELECT 1 FROM hosted_snapshot_generations) OR EXISTS(SELECT 1 FROM hosted_snapshot_pointer)')
        if cursor.fetchone()[0]:
            raise ValueError('Staging seed requires empty hosted Snapshot tables; existing data preserved')
        cursor.execute('INSERT INTO hosted_snapshot_generations (generation_id, data_classification, read_model) VALUES (%s, %s, %s)',
                       (generation, 'synthetic', Json(model)))
        cursor.execute('INSERT INTO hosted_snapshot_pointer (singleton, generation_id) VALUES (true, %s)', (generation,))
    print('Published one synthetic generation. Verify through the authenticated Worker; no private data printed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['generate', 'seed-synthetic'])
    args = parser.parse_args()
    if args.command == 'generate':
        destination = Path(__file__).resolve().parents[1] / 'hosted' / 'synthetic.fixture'
        destination.write_text(json.dumps(synthetic_read_model(), indent=2) + '\n', encoding='utf-8')
        print('Generated synthetic-only canonical fixture locally.')
    else:
        seed_synthetic()


if __name__ == '__main__':
    main()
