"""Durable upload processor. All ledger interpretation stays in canonical Python.

Run once in a hosted Actions job: python -m backend.import_jobs
Raw files are retained privately for replay/audit; neither rows nor errors are logged.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from dataclasses import dataclass

import pandas as pd

from backend.engine.calculation import calculate_portfolio, ObservedPrice
from backend.ingestion import TransactionIngestionService


class PublicationConflict(Exception):
    """Accepted generation or shared targets changed while an import was staged."""


@dataclass(frozen=True)
class ProcessingOutcome:
    state: str
    diagnostics: tuple[str, ...] = ()
    generation_id: str | None = None
    calculation_settings_version: str | None = None
    rebalancing_targets_version: str | None = None

    def __bool__(self):
        return self.state in ('completed', 'failed')


def stage_generation(sources, *, settings, quotes, cutoff, historical_input=None):
    transactions = pd.DataFrame()
    for source in sources:
        result = TransactionIngestionService(transactions).ingest_csv(source)
        if not result.accepted:
            raise ValueError('import_requires_review: ' + ','.join(result.diagnostics))
        if result.rows_processed == 0:
            raise ValueError('empty_import')
        transactions = pd.concat([transactions, result.transactions], ignore_index=True)
    ledger_version = hashlib.sha256(b''.join(hashlib.sha256(s).digest() for s in sources)).hexdigest()
    settings_version = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    model = calculate_portfolio(transactions, settings=settings, observed_prices=quotes,
                               ledger_version=ledger_version, settings_version=settings_version,
                               cutoff=cutoff).to_read_model()
    from backend.engine.history import calculate_history
    history = historical_input or {}
    model['portfolio_history'] = calculate_history(transactions, settings=settings,
        daily_prices={at: {symbol: ObservedPrice(**quote) for symbol, quote in quotes.items()}
                      for at, quotes in history.get('daily_prices', {}).items()},
        asset_coverage=history.get('asset_coverage', {}), market_closures=history.get('market_closures', {}),
        ledger_version=ledger_version, settings_version=settings_version, now=cutoff)
    return model


def process_next(connection, settings, historical_input=None):
    """One atomic publication; rollback retains accepted pointer and prior sources.

    Session advisory lock serializes import/history processors. Other publishers
    use pointer/settings checks under the same lock order as current valuation.
    A processing status is committed before work; abandoned jobs are retryable.
    """
    from psycopg2.extras import Json
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(470047)')
        if not cursor.fetchone()[0]:
            return ProcessingOutcome('idle')
        try:
            cursor.execute("SELECT job_id, csv_content FROM hosted_import_jobs WHERE state='pending' ORDER BY created_at, job_id LIMIT 1")
            job = cursor.fetchone()
            if not job:
                connection.commit()
                return ProcessingOutcome('idle')
            job_id, content = job
            cursor.execute("UPDATE hosted_import_jobs SET state='processing', updated_at=now(), attempts=attempts+1 WHERE job_id=%s", (job_id,))
            connection.commit()
            try:
                cursor.execute('SELECT csv_content FROM hosted_import_jobs WHERE state=\'completed\' ORDER BY completed_at, job_id')
                sources = [bytes(row[0]) for row in cursor.fetchall()] + [bytes(content)]
                # One MVCC read captures generation + shared targets before staging.
                cursor.execute('''SELECT p.generation_id, g.read_model, t.version::text
                    FROM hosted_targets t LEFT JOIN hosted_snapshot_pointer p ON p.singleton=true
                    LEFT JOIN hosted_snapshot_generations g ON g.generation_id=p.generation_id
                    WHERE t.singleton=true''')
                previous = cursor.fetchone()
                if not previous:
                    raise ValueError('shared_targets_unavailable')
                expected_generation, previous_model, expected_targets = previous
                previous_model = previous_model or {}
                quotes = {symbol: ObservedPrice(**quote) for symbol, quote in previous_model.get('observed_prices', {}).items()}
                model = stage_generation(sources, settings=settings, quotes=quotes, cutoff=datetime.now(timezone.utc).isoformat(), historical_input=historical_input)
                # Keep accounting-evidence configuration distinct from shared targets.
                model['import_provenance'] = {'calculation_settings_version': model['settings_version'],
                                             'rebalancing_targets_version': expected_targets}
                # Missing mapping/quote/fee evidence remains explicit in the canonical model;
                # a failed parse or review blocker never reaches publication.
                generation = str(uuid4())
                # Lock pointer first, targets second, matching hosted_publish_valuation.
                cursor.execute('SELECT generation_id FROM hosted_snapshot_pointer WHERE singleton=true FOR UPDATE')
                current_pointer = cursor.fetchone()
                current_generation = current_pointer[0] if current_pointer else None
                cursor.execute('SELECT version::text FROM hosted_targets WHERE singleton=true FOR SHARE')
                current_targets = cursor.fetchone()
                if current_generation != expected_generation or not current_targets or current_targets[0] != expected_targets:
                    raise PublicationConflict()
                cursor.execute("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES (%s,'private',%s)", (generation, Json(model)))
                if expected_generation is None:
                    cursor.execute('INSERT INTO hosted_snapshot_pointer(singleton,generation_id) VALUES(true,%s) ON CONFLICT(singleton) DO NOTHING', (generation,))
                else:
                    cursor.execute('UPDATE hosted_snapshot_pointer SET generation_id=%s WHERE singleton=true AND generation_id=%s', (generation, expected_generation))
                if cursor.rowcount != 1:
                    raise PublicationConflict()
                periods = model['portfolio_history']['periods'].values()
                history_state = 'completed' if periods and all(period['state'] == 'ready' for period in periods) else 'unavailable'
                cursor.execute("UPDATE hosted_import_jobs SET state='completed', generation_id=%s, diagnostics=%s, history_state=%s, completed_at=now(), updated_at=now() WHERE job_id=%s", (generation, Json(model['diagnostics']), history_state, job_id))
                connection.commit()
                outcome = ProcessingOutcome('completed', tuple(model['diagnostics']), generation,
                                            model['settings_version'], expected_targets)
            except Exception as error:
                connection.rollback()
                # Do not expose exception text (may include private CSV values or credentials).
                diagnostic = ('publication_conflict_retry' if isinstance(error, PublicationConflict)
                              else 'validation_requires_review' if isinstance(error, ValueError) else 'processing_failed')
                cursor.execute("UPDATE hosted_import_jobs SET state='failed', diagnostics=%s, updated_at=now() WHERE job_id=%s", (Json([diagnostic]), job_id))
                connection.commit()
                outcome = ProcessingOutcome('failed', (diagnostic,))
            return outcome
        finally:
            cursor.execute('SELECT pg_advisory_unlock(470047)')
            connection.commit()


def rebuild_history(connection, settings):
    """Daily hosted background work, independent of new uploads; atomic CAS publish.

    Public history calls happen before the database transaction. Provider errors
    retain the complete previous generation. CSV bytes and API keys are not logged.
    """
    from backend.providers.history import fetch_history_input
    from psycopg2.extras import Json
    now = datetime.now(timezone.utc).isoformat()
    historical_input = fetch_history_input(settings, now=now, api_key=os.environ.get('COINGECKO_DEMO_API_KEY'))
    if not historical_input['daily_prices']:
        return False
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(470047)')
        if not cursor.fetchone()[0]:
            return False
        try:
            cursor.execute('SELECT g.generation_id, g.read_model FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id) WHERE singleton=true')
            previous = cursor.fetchone()
            if not previous:
                return False
            previous_id, previous_model = previous
            cursor.execute("SELECT csv_content FROM hosted_import_jobs WHERE state='completed' ORDER BY completed_at, job_id")
            sources = [bytes(row[0]) for row in cursor.fetchall()]
            if not sources:
                return False
            quotes = {symbol: ObservedPrice(**quote) for symbol, quote in previous_model.get('observed_prices', {}).items()}
            model = stage_generation(sources, settings=settings, quotes=quotes, cutoff=now, historical_input=historical_input)
            generation = str(uuid4())
            cursor.execute("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES (%s,'private',%s)", (generation, Json(model)))
            cursor.execute('UPDATE hosted_snapshot_pointer SET generation_id=%s WHERE singleton=true AND generation_id=%s', (generation, previous_id))
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            connection.commit()
            return True
        finally:
            cursor.execute('SELECT pg_advisory_unlock(470047)')
            connection.commit()


def main():
    import argparse
    import psycopg2
    parser = argparse.ArgumentParser()
    parser.add_argument('--history-only', action='store_true')
    args = parser.parse_args()
    # Explicit verified evidence configuration; never silently assume private baselines.
    settings = json.loads(os.environ['IMPORT_CALCULATION_SETTINGS'])
    history_path = os.environ.get('IMPORT_HISTORY_FILE')
    historical_input = json.loads(Path(history_path).read_text(encoding='utf-8')) if history_path else None
    with psycopg2.connect(os.environ['DATABASE_URL']) as connection:
        if args.history_only:
            try:
                rebuild_history(connection, settings)
            except Exception:
                connection.rollback()
                raise SystemExit('History refresh failed; prior accepted generation retained.') from None
            return
        for _ in range(10):
            if not process_next(connection, settings, historical_input):
                break


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Import runner failed; accepted generation preserved. Review configuration privately.') from None
