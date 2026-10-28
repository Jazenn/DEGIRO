"""Manual, synthetic-only hosted import rehearsal in a disposable schema.

This never enables browser imports or configures the private publisher. Its only
output is sanitized verification status; source records and credentials stay out
of Actions logs. The existing public staging state is read, never changed.
"""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from backend.staging_connection import checked_staging_url


def fixture():
    """Invented EUR1000 acquisition + EUR5 fee, observed value EUR1100."""
    from backend.engine.calculation import ObservedPrice
    header = b'Date,Time,Product,ISIN,Description,Amount,,Order Id\n'
    rows = [b'02-01-2026,09:00,,,Deposit,EUR,1005,\n',
            b'03-01-2026,09:00,Synthetic Fund,SYNTHETIC-A,Buy 1 @ 1000 EUR,EUR,-1000,synthetic-buy\n',
            b'03-01-2026,09:01,Synthetic Fund,SYNTHETIC-A,Transaction fee,EUR,-5,synthetic-buy\n']
    settings = {
        'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'invented fixture only'},
        'cost_history': {'verified': True, 'evidence': 'complete invented records only'},
        'opening_baseline': {'at': '2026-01-01T00:00:00Z', 'cash_eur': '0', 'equity_eur': '0',
                             'verified': True, 'evidence': 'invented first funding only'},
        'asset_evidence': {'SYNTHETIC-A': {'verified': True, 'symbol': 'SYNTHETIC', 'kind': 'ETF',
                                        'evidence': 'invented Asset, not a broker mapping'}},
    }
    quotes = {'SYNTHETIC': ObservedPrice('1100', '2026-01-10T00:00:00Z', 'synthetic-rehearsal-only')}
    return header + b''.join(rows), header + b''.join(reversed(rows)), settings, quotes


def rehearse(connection):
    """Run real publisher transactions; cleanup only the newly owned namespace."""
    from psycopg2 import Binary, sql
    from psycopg2.extras import Json
    from backend.import_jobs import process_next, stage_generation
    with connection.cursor() as cursor:
        cursor.execute('SELECT count(*),bool_and(data_classification=\'synthetic\') FROM public.hosted_snapshot_generations')
        count, synthetic = cursor.fetchone()
        if not count or synthetic is not True:
            raise ValueError('synthetic_staging_required')
        cursor.execute('SELECT generation_id FROM public.hosted_snapshot_pointer WHERE singleton')
        original_pointer = cursor.fetchone()
        if not original_pointer:
            raise ValueError('accepted_synthetic_staging_required')
    namespace = 'staging_import_' + uuid4().hex
    root = Path(__file__).resolve().parents[1]
    source, overlap, settings, quotes = fixture()
    checks = []
    created = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(namespace)))
            created = True
            cursor.execute(sql.SQL('SET search_path TO {},pg_temp').format(sql.Identifier(namespace)))
            for schema in ('schema', 'targets-schema', 'import-schema'):
                content = (root / 'hosted' / (schema + '.sql')).read_text(encoding='utf-8')
                cursor.execute('\n'.join(line for line in content.splitlines()
                                         if line.strip() not in ('BEGIN;', 'COMMIT;')))
            initial = stage_generation([source], settings=settings, quotes=quotes,
                                       cutoff='2026-01-11T00:00:00Z')
            initial['rebalancing_targets_version'] = '0'
            cursor.execute("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('synthetic-rehearsal-baseline','synthetic',%s)", (Json(initial),))
            cursor.execute("INSERT INTO hosted_snapshot_pointer VALUES(true,'synthetic-rehearsal-baseline')")
        connection.commit()

        def enqueue(content):
            with connection.cursor() as cursor:
                cursor.execute('''INSERT INTO hosted_import_jobs(job_id,content_hash,csv_content)
                    VALUES(%s,%s,%s) ON CONFLICT(content_hash) DO UPDATE SET content_hash=excluded.content_hash
                    RETURNING job_id,state''', (str(uuid4()), hashlib.sha256(content).hexdigest(), Binary(content)))
                result = cursor.fetchone()
            connection.commit()
            return result

        def pointer():
            with connection.cursor() as cursor:
                cursor.execute('SELECT generation_id FROM hosted_snapshot_pointer WHERE singleton')
                return cursor.fetchone()[0]

        bad_job, _ = enqueue(b'not,a,supported,file\n')
        failed = process_next(connection, settings)
        if failed.state != 'failed' or pointer() != 'synthetic-rehearsal-baseline':
            raise ValueError('failed_import_replaced_generation')
        with connection.cursor() as cursor:
            cursor.execute("UPDATE hosted_import_jobs SET state='pending',diagnostics='[]',updated_at=now() WHERE job_id=%s AND state='failed' RETURNING job_id", (bad_job,))
            if not cursor.fetchone():
                raise ValueError('failed_import_not_retryable')
        connection.commit()
        if process_next(connection, settings).state != 'failed' or pointer() != 'synthetic-rehearsal-baseline':
            raise ValueError('failed_retry_replaced_generation')
        checks.append('failed import and retry retain previous accepted generation')

        good_job, _ = enqueue(source)
        if enqueue(source)[0] != good_job:
            raise ValueError('repeated_upload_created_another_job')
        completed = process_next(connection, settings)
        if completed.state != 'completed' or pointer() != completed.generation_id:
            raise ValueError('valid_import_did_not_publish')
        if enqueue(source) != (good_job, 'completed') or process_next(connection, settings).state != 'idle':
            raise ValueError('completed_upload_replayed')
        checks.append('repeated identical uploads reuse one job and do not replay publication')
        enqueue(overlap)
        second = process_next(connection, settings)
        if second.state != 'completed' or second.generation_id == completed.generation_id:
            raise ValueError('overlap_import_did_not_publish')
        with connection.cursor() as cursor:
            cursor.execute('''SELECT g.read_model,j.history_state FROM hosted_snapshot_pointer p
                JOIN hosted_snapshot_generations g USING(generation_id)
                JOIN hosted_import_jobs j USING(generation_id) WHERE p.singleton''')
            model, history_state = cursor.fetchone()
            ledger = model['ledger']
            if (ledger['cash_balance_eur'], ledger['net_external_contributions_eur'], ledger['net_gain_eur'],
                    ledger['positions'][0]['retained_cost_eur']) != ('0', '1005', '95', '1005'):
                raise ValueError('canonical_money_example_did_not_reconcile')
            if history_state != 'unavailable' or model['rebalancing_targets_version'] != '0':
                raise ValueError('history_or_target_provenance_incorrect')
            cursor.execute('SELECT attempts FROM hosted_import_jobs WHERE job_id=%s', (bad_job,))
            if cursor.fetchone()[0] != 2:
                raise ValueError('retry_attempts_not_recorded')
        checks.append('overlapping CSVs preserve canonical holdings, costs, cash and gains')
        checks.append('history remains explicitly unavailable independently of successful publication')
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute('SET search_path TO public,pg_temp')
            if created:
                # Only this run's generated namespace can be removed.
                cursor.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(namespace)))
        connection.commit()
    with connection.cursor() as cursor:
        cursor.execute('SELECT generation_id FROM public.hosted_snapshot_pointer WHERE singleton')
        if cursor.fetchone() != original_pointer:
            raise ValueError('public_staging_changed_during_rehearsal')
        cursor.execute('SELECT EXISTS(SELECT FROM pg_namespace WHERE nspname=%s)', (namespace,))
        if cursor.fetchone()[0]:
            raise ValueError('temporary_schema_cleanup_failed')
    checks.append('temporary schema removed and original public staging generation unchanged')
    return {'state': 'passed', 'scope': 'synthetic isolated hosted publisher', 'checks': checks}


def main():
    url = os.environ.get('STAGING_PUBLISHER_DATABASE_URL', '')
    try:
        if os.environ.get('STAGING_IMPORT_REHEARSAL_APPROVED') != 'synthetic-staging-only':
            raise ValueError('Approval required')
        checked_staging_url(url, os.environ.get('STAGING_EXPECTED_HOST'),
                            os.environ.get('STAGING_EXPECTED_DATABASE'))
    except Exception:
        print('{"state":"failed","reason":"destination_rejected"}')
        return 1
    # Both URL and effective libpq checks precede any network access.
    import psycopg2
    try:
        with psycopg2.connect(url, connect_timeout=15) as connection:
            result = rehearse(connection)
    except Exception:
        print('{"state":"failed","reason":"staging_rehearsal_failed"}')
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
