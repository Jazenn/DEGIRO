"""Full-archive application recovery restricted to approved synthetic staging.

Archives and private subprocess diagnostics live only in a restricted temporary
directory. The source is read-only; rollback checks run on the disposable copy.
The reviewed cloud_admin-owned future-object defaults are explicitly excluded
from replay; full platform metadata equality is never claimed.
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
from backend.staging_connection import checked_staging_url


def phase(name):
    """Static progress labels only: never exception text, SQL or object values."""
    print(json.dumps({'recovery_phase': name}), flush=True)


def report_client_failure(process):
    """Closed diagnostic vocabulary; raw client/server messages never escape."""
    errors = b'\n'.join(line.split(b'ERROR:', 1)[1].strip()
                        for line in process.stderr.splitlines() if b'ERROR:' in line)
    patterns = [
        ('public_schema_exists', rb'schema\s+"public"\s+already exists'),
        ('schema_exists', rb'schema\s+"[^"\r\n]+"\s+already exists'),
        ('relation_exists', rb'relation\s+"[^"\r\n]+"\s+already exists'),
        ('permission_denied', rb'permission denied|must be (?:owner|superuser)|only superuser'),
        ('missing_role', rb'role\s+"[^"\r\n]+"\s+does not exist'),
        ('extension_unavailable', rb'extension.*(?:not available|does not exist|not installed)'),
        ('unrecognized_setting', rb'unrecognized configuration parameter'),
        ('snapshot_unavailable', rb'(?:invalid|does not exist|could not import).*snapshot'),
    ]
    category = next((name for name, pattern in patterns if re.search(pattern, errors, re.I)), None)
    if category is None and re.search(rb'connection.*(?:failed|refused|timed out)|could not connect', process.stderr, re.I):
        category = 'connection_failed'
    command = process.stderr.split(b'Command was:', 1)[1].lstrip() if b'Command was:' in process.stderr else b''
    statement_patterns = [
        ('schema_comment', rb'^COMMENT\s+ON\s+SCHEMA\b'),
        ('schema_acl', rb'^(?:GRANT|REVOKE)\b[^;]*\bON\s+SCHEMA\b'),
        ('schema_owner', rb'^ALTER\s+SCHEMA\b[^;]*\bOWNER\b'),
        ('default_privileges', rb'^ALTER\s+DEFAULT\s+PRIVILEGES\b'),
        ('role_switch', rb'^SET\s+(?:SESSION\s+AUTHORIZATION|ROLE)\b'),
        ('extension', rb'^(?:CREATE|ALTER|COMMENT\s+ON)\s+EXTENSION\b'),
        ('object_acl', rb'^(?:GRANT|REVOKE)\b'),
        ('object_comment', rb'^COMMENT\s+ON\b'),
        ('object_owner', rb'^ALTER\b[^;]*\bOWNER\b'),
        ('object_create', rb'^CREATE\b'),
        ('table_alter', rb'^ALTER\s+TABLE\b'),
        ('copy_data', rb'^COPY\b'),
        ('sequence_state', rb'^SELECT\s+pg_catalog\.setval\b'),
        ('session_setting', rb'^SET\b'),
    ]
    statement_kind = next((name for name, pattern in statement_patterns if re.search(pattern, command, re.I)), 'other')
    permission_kind = next((kind for kind in ('schema', 'table', 'sequence', 'function', 'role', 'extension', 'database')
                            if re.search(rb'(?:permission denied for|must be owner of)\s+'+kind.encode()+rb'\b', errors, re.I)), None)
    print(json.dumps({'client_exit_code': process.returncode,
                      'client_warning_present': bool(process.stderr),
                      'client_failure_categories': [category or 'other'],
                      'client_failure_statement_kind': statement_kind,
                      'permission_target_kind': permission_kind}), flush=True)


def verify_capture(restored, expected):
    actual = capture(restored)
    # Provider-owned future-object defaults are the one explicitly reviewed
    # exception. Every application-owned default and every explicit ACL remains
    # part of exact equality, including unexpected destination defaults.
    application_expected = {**expected, 'default_privileges': [row for row in expected['default_privileges'] if row[0] != 'cloud_admin']}
    differences = [category for category in application_expected if actual[category] != application_expected[category]]
    if differences:
        print(json.dumps({'comparison_mismatch_categories': differences}), flush=True)
        raise ValueError('Recovery comparison failed')


def default_acl_records(connection):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT d.oid::bigint,'pg_default_acl'::regclass::oid::bigint,
            pg_get_userbyid(d.defaclrole),coalesce(n.nspname,''),d.defaclobjtype::text,d.defaclacl::text,
            (SELECT count(*) FROM aclexplode(d.defaclacl))
            FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
            ORDER BY 3,4,5""")
        return cursor.fetchall()


def reviewed_provider_defaults(records):
    provider = [row for row in records if row[2] == 'cloud_admin']
    # This is the exact observed and reviewed staging exception, not a general
    # policy of discarding unassumable roles or all DEFAULT ACL records.
    if (len(provider) != 2 or sum(row[6] for row in provider) != 9
            or {row[4] for row in provider} != {'r', 'S'}
            or any(row[3] not in ('', 'public') for row in provider)):
        raise ValueError('Provider default privilege exception changed')
    return provider


def selected_restore_list(content, provider):
    wanted = {(row[1], row[0]) for row in provider}
    seen, selected = set(), []
    for line in content.splitlines(keepends=True):
        record = re.match(rb'^\d+;\s+(\d+)\s+(\d+)\s+(.+)', line)
        key = (int(record[1]), int(record[2])) if record else None
        if key in wanted:
            if key in seen or not record[3].startswith(b'DEFAULT ACL '):
                raise ValueError('Unmapped provider default ACL archive entry')
            seen.add(key)
            selected.append(b';'+line)
        else:
            selected.append(line)
    if seen != wanted:
        raise ValueError('Provider default ACL archive entry missing')
    return b''.join(selected)


def verify_worker_privileges(connection, role=None):
    with connection.cursor() as cursor:
        if role is None:
            cursor.execute("""SELECT DISTINCT r.rolname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL aclexplode(c.relacl) a JOIN pg_roles r ON r.oid=a.grantee
                WHERE n.nspname='public' AND c.relname='hosted_snapshot_generations'
                AND a.privilege_type='SELECT' AND r.oid<>c.relowner AND r.rolcanlogin
                AND has_table_privilege(r.oid,'public.hosted_sessions','INSERT')
                AND has_table_privilege(r.oid,'public.hosted_sessions','DELETE')
                AND NOT has_table_privilege(r.oid,'public.hosted_snapshot_generations','UPDATE')""")
            candidates = cursor.fetchall()
            if len(candidates) != 1:
                raise ValueError('Expected one restricted Worker role')
            role = candidates[0][0]
        reads = ['hosted_snapshot_generations', 'hosted_snapshot_pointer', 'hosted_targets',
                 'hosted_execution_terms', 'hosted_contribution_assets', 'hosted_quote_mappings',
                 'hosted_crypto_market_history', 'hosted_crypto_sale_permissions', 'hosted_crypto_plan_state',
                 'hosted_crypto_plan_history', 'hosted_crypto_plan_operations', 'hosted_crypto_sale_costs',
                 'hosted_owner_identity', 'hosted_sessions']
        cursor.execute("SELECT bool_and(has_table_privilege(%s,t,'SELECT')) FROM unnest(%s::text[]) t",
                       (role, ['public.'+table for table in reads]))
        if cursor.fetchone()[0] is not True:
            raise ValueError('Worker read privileges changed')
        functions = ['hosted_save_targets(text,bigint,jsonb)',
                     'hosted_publish_valuation(text,text,bigint,jsonb,timestamptz)',
                     'hosted_accept_crypto_plan(jsonb,jsonb)', 'hosted_read_crypto_executions(text)',
                     'hosted_record_crypto_execution(jsonb)', 'hosted_review_crypto_replacement(jsonb)',
                     'hosted_cancel_crypto_report(jsonb)', 'hosted_read_crypto_report_events(text)']
        cursor.execute("SELECT bool_and(has_function_privilege(%s,f,'EXECUTE')) FROM unnest(%s::text[]) f",
                       (role, ['public.'+function for function in functions]))
        if cursor.fetchone()[0] is not True:
            raise ValueError('Worker operation privileges changed')
        protected = ['hosted_snapshot_generations', 'hosted_snapshot_pointer', 'hosted_crypto_plan_state',
                     'hosted_crypto_plan_history', 'hosted_crypto_plan_events', 'hosted_crypto_reports',
                     'hosted_crypto_match_allocations', 'hosted_crypto_execution_capacity', 'hosted_crypto_execution_state',
                     'hosted_crypto_report_events', 'hosted_crypto_execution_operations', 'hosted_crypto_plan_operations']
        cursor.execute("SELECT bool_and(NOT has_table_privilege(%s,t,p)) FROM unnest(%s::text[]) t CROSS JOIN unnest(%s::text[]) p",
                       (role, ['public.'+table for table in protected], ['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']))
        if cursor.fetchone()[0] is not True:
            raise ValueError('Worker can directly mutate protected state')
        cursor.execute("SELECT has_column_privilege(%s,'public.hosted_import_jobs','csv_content','SELECT')", (role,))
        if cursor.fetchone()[0] is not False:
            raise ValueError('Worker can read raw source bytes')
        for table, permission in [('hosted_owner_identity', 'INSERT'), ('hosted_sessions', 'INSERT'), ('hosted_sessions', 'DELETE')]:
            cursor.execute('SELECT has_table_privilege(%s,%s,%s)', (role, 'public.'+table, permission))
            if cursor.fetchone()[0] is not True:
                raise ValueError('Worker session privileges changed')
    return role


def approved_source(environment):
    """Resolve only the independently configured, direct staging endpoint."""
    url = checked_staging_url(environment['STAGING_PUBLISHER_DATABASE_URL'],
                              environment.get('STAGING_EXPECTED_HOST'),
                              environment.get('STAGING_EXPECTED_DATABASE'))
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
                schema_grants=schema_grants,
                default_privileges=[row[2:] for row in default_acl_records(connection)])


def synthetic_only(connection):
    with connection.cursor() as cursor:
        # This rehearsal compares the application's public-schema layout. Never
        # export unclassified user data in another schema or an unsupported kind
        # of relation and then falsely claim that it was compared.
        cursor.execute("""SELECT EXISTS(SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
            AND c.relkind IN ('r','p','v','m','f','S','c')
            AND NOT EXISTS(SELECT FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e')
            AND (n.nspname<>'public' OR c.relkind NOT IN ('r','p','S') OR c.relpersistence<>'p'))""")
        if cursor.fetchone()[0]:
            raise ValueError('Unexpected application schema or relation kind')
        cursor.execute("""SELECT EXISTS(SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
            AND NOT EXISTS(SELECT FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e')
            AND (n.nspname<>'public' OR p.prokind<>'f'))""")
        if cursor.fetchone()[0]:
            raise ValueError('Unexpected application routine schema or kind')
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
                     'channel_binding': 'PGCHANNELBINDING', 'connect_timeout': 'PGCONNECT_TIMEOUT',
                     'application_name': 'PGAPPNAME'}[key]] = value
    if database:
        environment['PGDATABASE'] = database
    environment['PGCONNECT_TIMEOUT'] = '15'
    return environment


def rehearse(environment):
    url = approved_source(environment)
    phase('verify_clients')
    binary = Path(environment.get('PG_BIN', '/usr/lib/postgresql/17/bin'))
    clients = [binary / name for name in ('pg_dump', 'pg_restore')]
    if not all(client.is_file() for client in clients):
        raise ValueError('Compatible PostgreSQL clients required')
    for client in clients:
        version = subprocess.run([str(client), '--version'], capture_output=True, check=True, timeout=15)
        if not re.search(rb'\(PostgreSQL\) 17\.', version.stdout):
            raise ValueError('Review a server/client version change first')
    phase('connect_source')
    source = psycopg2.connect(url, connect_timeout=15)
    admin = None
    destination = 'degiro_recovery_probe_' + uuid4().hex
    created = False
    started = time.monotonic()
    try:
        phase('capture_source_snapshot')
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
        phase('fingerprint_source')
        expected = capture(source)
        provider_defaults = reviewed_provider_defaults(default_acl_records(source))
        phase('verify_source_worker_privileges')
        worker_role = verify_worker_privileges(source)
        with tempfile.TemporaryDirectory(prefix='degiro-private-recovery-') as directory:
            os.chmod(directory, 0o700)
            archive = Path(directory) / 'database.dump'
            phase('dump_archive')
            process = subprocess.run([str(clients[0]), '--format=custom', '--snapshot='+snapshot,
                                      '--file='+str(archive)], env=pg_environment(url),
                                     capture_output=True, timeout=240)
            if process.returncode or process.stderr:
                report_client_failure(process)
                raise ValueError('Dump failed or emitted a warning')
            archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            phase('inspect_archive_schema')
            schema_script = Path(directory) / 'schema.sql'
            inspection = subprocess.run([str(clients[1]), '--schema-only', '--no-owner',
                                         '--file='+str(schema_script), str(archive)],
                                        env=pg_environment(url), capture_output=True, timeout=60)
            if inspection.returncode or inspection.stderr:
                report_client_failure(inspection)
                raise ValueError('Archive inspection failed')
            creates_public = bool(re.search(rb'^CREATE SCHEMA (?:public|"public");\s*$',
                                            schema_script.read_bytes(), re.M))
            private_schema_sql = schema_script.read_bytes()
            print(json.dumps({'archive_creates_public_schema': creates_public,
                              'archive_comments_public_schema': bool(re.search(rb'^COMMENT ON SCHEMA (?:public|"public")\b', private_schema_sql, re.M)),
                              'archive_has_default_privileges': bool(re.search(rb'^ALTER DEFAULT PRIVILEGES\b', private_schema_sql, re.M)),
                              'archive_has_role_switch': bool(re.search(rb'^SET (?:ROLE|SESSION AUTHORIZATION)\b', private_schema_sql, re.M))}), flush=True)
            phase('select_reviewed_provider_default_exception')
            original_list = Path(directory) / 'complete.list'
            listing = subprocess.run([str(clients[1]), '--list', '--file='+str(original_list), str(archive)],
                                     env=pg_environment(url), capture_output=True, timeout=60)
            if listing.returncode or listing.stderr:
                report_client_failure(listing)
                raise ValueError('Archive listing failed')
            restore_list = Path(directory) / 'application-restore.list'
            restore_list.write_bytes(selected_restore_list(original_list.read_bytes(), provider_defaults))
            print(json.dumps({'provider_default_acl_entries_not_restored': len(provider_defaults),
                              'provider_default_grants_not_restored': sum(row[6] for row in provider_defaults),
                              'full_platform_metadata_equal': False}), flush=True)
            # Snapshot remains open through the dump and comparison capture.
            source.rollback()
            admin = psycopg2.connect(url, connect_timeout=15)
            admin.autocommit = True
            phase('create_isolated_database')
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0 OWNER {}').format(sql.Identifier(destination), sql.Identifier(owner)))
                created = True
                cursor.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(destination)))
            restored_url = {**parse_dsn(url), 'dbname': destination}
            phase('verify_empty_destination')
            with closing(psycopg2.connect(**restored_url)) as restored:
                with restored.cursor() as cursor:
                    cursor.execute("SELECT EXISTS(SELECT FROM pg_tables WHERE schemaname='public')")
                    if cursor.fetchone()[0]:
                        raise ValueError('Restore destination is not empty')
            # All explicit ACLs and application defaults remain selected. Only
            # the reviewed provider-owned DEFAULT ACL catalog OIDs are excluded;
            # the complete archive itself remains unchanged.
            # No --clean or --create option can target the source database.
            phase('restore_archive')
            process = subprocess.run([str(clients[1]), '--dbname='+destination, '--single-transaction',
                                      '--exit-on-error', '--no-owner', '--use-list='+str(restore_list), str(archive)],
                                     env=pg_environment(url, destination), capture_output=True, timeout=240)
            if process.returncode or process.stderr:
                report_client_failure(process)
                raise ValueError('Restore failed or emitted a warning')
            with closing(psycopg2.connect(**restored_url)) as restored:
                phase('compare_restored_capture')
                verify_capture(restored, expected)
                phase('verify_restored_worker_privileges')
                verify_worker_privileges(restored, worker_role)
                restored.rollback()
                phase('verify_restored_rollback')
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
                    phase('verify_restored_immutability')
                    with restored.cursor() as cursor:
                        cursor.execute('UPDATE hosted_snapshot_generations SET published_at=published_at WHERE generation_id=%s', (accepted,))
                except psycopg2.Error as error:
                    if error.pgcode != 'P0001':
                        raise
                    restored.rollback()
                else:
                    raise ValueError('Immutable generation accepted mutation')
                phase('compare_after_rollback')
                verify_capture(restored, expected)
            return {'state': 'application_recovery_passed', 'scope': 'synthetic application recovery; provider defaults excluded',
                    'public_tables': len(expected['data']), 'archive_sha256': archive_digest,
                    'application_data_schema_explicit_grants_equal': True,
                    'worker_effective_privileges_verified': True,
                    'provider_default_acl_entries_not_restored': len(provider_defaults),
                    'provider_default_grants_not_restored': sum(row[6] for row in provider_defaults),
                    'full_platform_metadata_equal': False, 'rollback_and_immutability_verified': True,
                    'duration_seconds': round(time.monotonic()-started, 2),
                    'archive_retention': 'ephemeral private runner only; no durable backup claimed'}
    finally:
        phase('cleanup_owned_resources')
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
    except Exception as error:
        print('Staging recovery rehearsal failed; credentials and database content withheld.')
        trace = error.__traceback__
        while trace.tb_next:
            trace = trace.tb_next
        sqlstate = getattr(error, 'pgcode', None)
        print(json.dumps({'state': 'failed', 'exception_type': type(error).__name__,
                          'line': trace.tb_lineno,
                          'sqlstate': sqlstate if isinstance(sqlstate, str) and re.fullmatch(r'[A-Z0-9]{5}', sqlstate) else None}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
