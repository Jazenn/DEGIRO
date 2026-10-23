"""Durable upload processor. All ledger interpretation stays in canonical Python.

Run once in a hosted Actions job: python -m backend.import_jobs
Raw files are retained privately for replay/audit; neither rows nor errors are logged.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from backend.engine.calculation import calculate_portfolio, ObservedPrice
from backend.ingestion import TransactionIngestionService


def stage_generation(sources, *, settings, quotes, cutoff):
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
    return calculate_portfolio(transactions, settings=settings, observed_prices=quotes,
                               ledger_version=ledger_version, settings_version=settings_version,
                               cutoff=cutoff).to_read_model()


def process_next(connection, settings):
    """One atomic publication; rollback retains accepted pointer and prior sources.

    Session advisory lock serializes publishers, including across workflow retries.
    A processing status is committed before work; abandoned jobs are retryable.
    """
    from psycopg2.extras import Json
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(470047)')
        if not cursor.fetchone()[0]:
            return False
        try:
            cursor.execute("SELECT job_id, csv_content FROM hosted_import_jobs WHERE state='pending' ORDER BY created_at, job_id LIMIT 1")
            job = cursor.fetchone()
            if not job:
                connection.commit()
                return False
            job_id, content = job
            cursor.execute("UPDATE hosted_import_jobs SET state='processing', updated_at=now(), attempts=attempts+1 WHERE job_id=%s", (job_id,))
            connection.commit()
            try:
                cursor.execute('SELECT csv_content FROM hosted_import_jobs WHERE state=\'completed\' ORDER BY completed_at, job_id')
                sources = [bytes(row[0]) for row in cursor.fetchall()] + [bytes(content)]
                cursor.execute('SELECT g.read_model FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id) WHERE singleton=true')
                previous = cursor.fetchone()
                previous_model = previous[0] if previous else {}
                quotes = {symbol: ObservedPrice(**quote) for symbol, quote in previous_model.get('observed_prices', {}).items()}
                model = stage_generation(sources, settings=settings, quotes=quotes, cutoff=datetime.now(timezone.utc).isoformat())
                # Missing mapping/quote/fee evidence remains explicit in the canonical model;
                # a failed parse or review blocker never reaches publication.
                generation = str(uuid4())
                cursor.execute("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES (%s,'private',%s)", (generation, Json(model)))
                cursor.execute('INSERT INTO hosted_snapshot_pointer(singleton,generation_id) VALUES(true,%s) ON CONFLICT(singleton) DO UPDATE SET generation_id=excluded.generation_id', (generation,))
                cursor.execute("UPDATE hosted_import_jobs SET state='completed', generation_id=%s, diagnostics=%s, history_state='unavailable', completed_at=now(), updated_at=now() WHERE job_id=%s", (generation, Json(model['diagnostics']), job_id))
                connection.commit()
            except Exception as error:
                connection.rollback()
                # Do not expose exception text (may include private CSV values or credentials).
                diagnostic = 'validation_requires_review' if isinstance(error, ValueError) else 'processing_failed'
                cursor.execute("UPDATE hosted_import_jobs SET state='failed', diagnostics=%s, updated_at=now() WHERE job_id=%s", (Json([diagnostic]), job_id))
                connection.commit()
            return True
        finally:
            cursor.execute('SELECT pg_advisory_unlock(470047)')
            connection.commit()


def main():
    import psycopg2
    # Explicit verified evidence configuration; never silently assume private baselines.
    settings = json.loads(os.environ['IMPORT_CALCULATION_SETTINGS'])
    with psycopg2.connect(os.environ['DATABASE_URL']) as connection:
        for _ in range(10):
            if not process_next(connection, settings):
                break


if __name__ == '__main__':
    main()
