"""Full database recovery rehearsal restricted to approved synthetic staging.

Archives and private subprocess diagnostics live only in a restricted temporary
directory. The source is read-only; rollback checks run on the disposable copy.
"""
import json
import os
from pathlib import Path
import hashlib
import re
import subprocess
import tempfile
import time
from contextlib import closing
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn


def approved_source(environment):
    """Resolve only the independently configured, direct staging endpoint."""
    url = environment['STAGING_PUBLISHER_DATABASE_URL']
    parts = urlsplit(url)
    if (environment.get('STAGING_BRANCH_ID') != 'br-tiny-moon-al8b0u31'
            or not environment.get('STAGING_EXPECTED_HOST')
            or parts.hostname != environment['STAGING_EXPECTED_HOST']
            or '-pooler' in parts.hostname
            or not parts.hostname.endswith('.neon.tech')
            or parts.scheme not in ('postgres', 'postgresql')
            or parse_qs(parts.query).get('sslmode') != ['require']
            or environment.get('STAGING_EXPECTED_DATABASE') != 'neondb'
            or not parts.username or not parts.password or parts.path != '/neondb'):
        raise ValueError('Unapproved synthetic staging endpoint')
    return url


def capture(connection):
    """Private exact data/schema/grant fingerprints from the caller's snapshot."""
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL TIME ZONE 'UTC'")
        cursor.execute("SET LOCAL DateStyle TO 'ISO, YMD'")
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables = [row[0] for row in cursor.fetchall()]
        data = {}
        for table in tables:
            cursor.execute(sql.SQL('SELECT md5(row_to_json(t)::text) FROM public.{} t ORDER BY 1').format(sql.Identifier(table)))
            digest, count = hashlib.sha256(), 0
            while rows := cursor.fetchmany(1000):
                for row in rows:
                    digest.update((row[0]+'\n').encode())
                    count += 1
            data[table] = (count, digest.hexdigest())
        cursor.execute("""SELECT p.proname,pg_get_function_identity_arguments(p.oid),pg_get_functiondef(p.oid),
            coalesce(p.proacl::text,'') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.prokind='f' ORDER BY 1,2""")
        functions = cursor.fetchall()
        cursor.execute("""SELECT c.relname,c.relkind,coalesce(c.relacl::text,''),
            a.attname,coalesce(a.attacl::text,'') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
            WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S') ORDER BY 1,4""")
        grants = cursor.fetchall()
        cursor.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t
            JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2""")
        triggers = cursor.fetchall()
        cursor.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' ORDER BY 1,2""")
        constraints = cursor.fetchall()
        cursor.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname")
        indexes = cursor.fetchall()
        cursor.execute("SELECT sequencename,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
        sequences = cursor.fetchall()
        cursor.execute("SELECT coalesce(nspacl::text,'') FROM pg_namespace WHERE nspname='public'")
        schema_grants = cursor.fetchall()
    return dict(data=data, functions=functions, grants=grants, triggers=triggers,
                constraints=constraints, indexes=indexes, sequences=sequences,
                schema_grants=schema_grants)


def synthetic_only(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS(SELECT FROM hosted_snapshot_generations), EXISTS(SELECT FROM hosted_snapshot_generations WHERE data_classification<>'synthetic')")
        populated, private = cursor.fetchone()
        if not populated or private:
            raise ValueError('Source is not exclusively synthetic')
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename NOT LIKE 'hosted\\_%' ESCAPE '\\'")
        for table, in cursor.fetchall():
            cursor.execute(sql.SQL('SELECT EXISTS(SELECT FROM public.{})').format(sql.Identifier(table)))
            if cursor.fetchone()[0]:
                raise ValueError('Legacy records must remain empty')
        # Retained uploads are not classified independently: refuse rather than
        # assume that any raw bytes in a synthetic database are invented.
        cursor.execute('SELECT EXISTS(SELECT FROM hosted_import_jobs)')
        if cursor.fetchone()[0]:
            raise ValueError('Recovery fixture requires no retained uploads')


def pg_environment(url, database=None):
    settings = parse_dsn(url)
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith('PG') and key != 'DATABASE_URL'
                   and not key.startswith('STAGING_')}
    for key, value in settings.items():
        environment[{'dbname': 'PGDATABASE', 'host': 'PGHOST', 'port': 'PGPORT',
                     'user': 'PGUSER', 'password': 'PGPASSWORD', 'sslmode': 'PGSSLMODE',
                     'channel_binding': 'PGCHANNELBINDING', 'options': 'PGOPTIONS'}[key]] = value
    if database:
        environment['PGDATABASE'] = database
    environment['PGCONNECT_TIMEOUT'] = '15'
    return environment


def rehearse(environment):
    url = approved_source(environment)
    binary = Path(environment.get('PG_BIN', '/usr/lib/postgresql/17/bin'))
    clients = [binary / name for name in ('pg_dump', 'pg_restore')]
    if not all(client.is_file() for client in clients):
        raise ValueError('Compatible PostgreSQL clients required')
    for client in clients:
        version = subprocess.run([str(client), '--version'], capture_output=True, check=True, timeout=15)
        if not re.search(rb'\(PostgreSQL\) 17\.', version.stdout):
            raise ValueError('Review a server/client version change first')
    source = psycopg2.connect(url, connect_timeout=15)
    admin = None
    destination = 'degiro_recovery_probe_' + uuid4().hex
    created = False
    started = time.monotonic()
    try:
        source.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with source.cursor() as cursor:
            cursor.execute('SHOW server_version_num')
            if int(cursor.fetchone()[0]) // 10000 != 17:
                raise ValueError('Unexpected staging server version')
            cursor.execute('SELECT current_database(),current_user')
            source_name, owner = cursor.fetchone()
            if source_name != 'neondb' or destination == source_name:
                raise ValueError('Unexpected source/destination')
            cursor.execute('SELECT pg_export_snapshot()')
            snapshot = cursor.fetchone()[0]
        synthetic_only(source)
        expected = capture(source)
        with tempfile.TemporaryDirectory(prefix='degiro-private-recovery-') as directory:
            os.chmod(directory, 0o700)
            archive = Path(directory) / 'database.dump'
            process = subprocess.run([str(clients[0]), '--format=custom', '--snapshot='+snapshot,
                                      '--file='+str(archive)], env=pg_environment(url),
                                     capture_output=True, timeout=240)
            if process.returncode or process.stderr:
                raise ValueError('Dump failed or emitted a warning')
            archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            # Snapshot remains open through the dump and comparison capture.
            source.rollback()
            admin = psycopg2.connect(url, connect_timeout=15)
            admin.autocommit = True
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0 OWNER {}').format(sql.Identifier(destination), sql.Identifier(owner)))
                created = True
                cursor.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(destination)))
            restored_url = {**parse_dsn(url), 'dbname': destination}
            with closing(psycopg2.connect(**restored_url)) as restored:
                with restored.cursor() as cursor:
                    cursor.execute("SELECT EXISTS(SELECT FROM pg_tables WHERE schemaname='public')")
                    if cursor.fetchone()[0]:
                        raise ValueError('Restore destination is not empty')
            # Same reviewed staging cluster and existing roles only. Preserve the
            # archive's ACLs, including PUBLIC revocations, then compare them.
            # No --clean or --create option can target the source database.
            process = subprocess.run([str(clients[1]), '--dbname='+destination, '--single-transaction',
                                      '--exit-on-error', '--no-owner', str(archive)],
                                     env=pg_environment(url, destination), capture_output=True, timeout=240)
            if process.returncode or process.stderr:
                raise ValueError('Restore failed or emitted a warning')
            with closing(psycopg2.connect(**restored_url)) as restored:
                if capture(restored) != expected:
                    raise ValueError('Restored data/schema/grants differ')
                restored.rollback()
                with restored.cursor() as cursor:
                    cursor.execute('SELECT generation_id FROM hosted_snapshot_pointer WHERE singleton FOR UPDATE')
                    accepted = cursor.fetchone()[0]
                    alternate = 'synthetic-rollback-probe-' + uuid4().hex
                    cursor.execute("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) SELECT %s,'synthetic',read_model FROM hosted_snapshot_generations WHERE generation_id=%s", (alternate, accepted))
                    cursor.execute('UPDATE hosted_snapshot_pointer SET generation_id=%s WHERE singleton AND generation_id=%s', (alternate, accepted))
                    if cursor.rowcount != 1:
                        raise ValueError('Restored publication CAS failed')
                restored.rollback()
                with restored.cursor() as cursor:
                    cursor.execute('SELECT generation_id FROM hosted_snapshot_pointer WHERE singleton')
                    if cursor.fetchone()[0] != accepted:
                        raise ValueError('Rollback lost accepted generation')
                try:
                    with restored.cursor() as cursor:
                        cursor.execute('UPDATE hosted_snapshot_generations SET published_at=published_at WHERE generation_id=%s', (accepted,))
                except psycopg2.Error as error:
                    if error.pgcode != 'P0001':
                        raise
                    restored.rollback()
                else:
                    raise ValueError('Immutable generation accepted mutation')
                if capture(restored) != expected:
                    raise ValueError('Rollback changed restored histories')
            return {'state': 'passed', 'scope': 'full synthetic staging database',
                    'public_tables': len(expected['data']), 'archive_sha256': archive_digest,
                    'data_schema_grants_equal': True, 'rollback_and_immutability_verified': True,
                    'duration_seconds': round(time.monotonic()-started, 2),
                    'archive_retention': 'ephemeral private runner only; no durable backup claimed'}
    finally:
        source.close()
        if admin:
            if created:
                # Only the database this invocation successfully created can be
                # dropped. Never terminate another session or use DROP ... FORCE.
                if not re.fullmatch(r'degiro_recovery_probe_[0-9a-f]{32}', destination):
                    raise ValueError('Unexpected cleanup target')
                with admin.cursor() as cursor:
                    cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(destination)))
            admin.close()


def main():
    try:
        result = rehearse(os.environ)
    except Exception:
        print('Staging recovery rehearsal failed; credentials and database content withheld.')
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
