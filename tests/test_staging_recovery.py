"""Recovery CLI must reject unapproved destinations before any database access."""
import os
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import psycopg2
import pytest
from backend.staging_recovery import rehearse


def test_recovery_cli_rejects_unapproved_endpoint_without_exposing_credentials():
    environment = {**os.environ, 'STAGING_PUBLISHER_DATABASE_URL':
                   'postgresql://owner:never-print-this@other.example.test/neondb?sslmode=require',
                   'STAGING_EXPECTED_HOST': 'approved.example.test',
                   'STAGING_EXPECTED_DATABASE': 'neondb',
                   'STAGING_BRANCH_ID': 'br-tiny-moon-al8b0u31'}
    result = subprocess.run([sys.executable, '-m', 'backend.staging_recovery'],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'Staging recovery rehearsal failed; credentials and database content withheld.' in result.stdout
    assert 'never-print-this' not in result.stdout + result.stderr
    assert result.stderr == ''


def test_recovery_failure_reports_safe_phase_and_exception_without_private_diagnostics(recovery_driver, monkeypatch, capsys):
    from backend.staging_recovery import main
    for key, value in recovery_driver.environment.items():
        monkeypatch.setenv(key, value)
    recovery_driver.private_stderr = b'password=never-print-this private financial record'
    assert main() == 1
    output = capsys.readouterr()
    assert 'never-print-this' not in output.out + output.err
    assert 'private financial record' not in output.out + output.err
    assert '"recovery_phase": "dump_archive"' in output.out
    diagnostic = json.loads(output.out.splitlines()[-1])
    assert diagnostic['state'] == 'failed'
    assert diagnostic['exception_type'] == 'ValueError'
    assert isinstance(diagnostic['line'], int)


def test_restore_error_classifier_distinguishes_public_schema_collision_without_private_sql(recovery_driver, monkeypatch, capsys):
    from backend.staging_recovery import main
    for key, value in recovery_driver.environment.items():
        monkeypatch.setenv(key, value)
    recovery_driver.schema_script = b'CREATE SCHEMA public;\n-- private-schema-text\n'
    recovery_driver.restore_stderr = b'pg_restore: error: could not execute query: ERROR:  schema "public" already exists\nCommand was: private-sql-content'
    assert main() == 1
    output = capsys.readouterr()
    assert '"archive_creates_public_schema": true' in output.out
    assert '"client_failure_categories": ["public_schema_exists"]' in output.out
    assert 'private-schema-text' not in output.out + output.err
    assert 'private-sql-content' not in output.out + output.err
    assert 'owned database dropped' in recovery_driver.events


@pytest.mark.parametrize('command,kind', [
    (b'COMMENT ON SCHEMA public IS \'private-comment\';', 'schema_comment'),
    (b'GRANT USAGE ON SCHEMA public TO private_role;', 'schema_acl'),
    (b'ALTER DEFAULT PRIVILEGES FOR ROLE private_role GRANT SELECT ON TABLES TO private_role;', 'default_privileges'),
    (b'SET SESSION AUTHORIZATION private_role;', 'role_switch'),
    (b'CREATE EXTENSION private_extension;', 'extension'),
])
def test_restore_permission_classifier_reports_only_safe_statement_kind(recovery_driver, monkeypatch, capsys, command, kind):
    from backend.staging_recovery import main
    for key, value in recovery_driver.environment.items():
        monkeypatch.setenv(key, value)
    recovery_driver.restore_stderr = b'pg_restore: error: could not execute query: ERROR:  permission denied for schema public\nCommand was: '+command
    assert main() == 1
    output = capsys.readouterr()
    assert '"client_failure_statement_kind": "'+kind+'"' in output.out
    assert '"permission_target_kind": "schema"' in output.out
    assert 'private-comment' not in output.out + output.err
    assert 'private_role' not in output.out + output.err
    assert 'private_extension' not in output.out + output.err


@pytest.fixture
def recovery_driver(monkeypatch, tmp_path):
    """External driver/process seam; psycopg contexts deliberately stay open."""
    connections, events = [], []
    class Immutable(psycopg2.Error):
        @property
        def pgcode(self):
            return 'P0001'

    class Cursor:
        rowcount = 1
        rows = []

        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement, params=None):
            query = statement if isinstance(statement, str) else repr(statement)
            self.rows = []
            if 'DROP DATABASE' in query:
                assert all(c.closed for c in connections if c.restored), 'Restored connections still open'
                events.append('owned database dropped')
            elif 'CREATE DATABASE' in query:
                events.append('owned database created')
            elif 'SHOW server_version_num' in query:
                self.rows = [('170011',)]
            elif 'current_database(),current_user' in query:
                self.rows = [('neondb', 'owner')]
            elif 'pg_export_snapshot()' in query:
                self.rows = [('00000001-1',)]
            elif 'FROM pg_default_acl d' in query:
                app_defaults = fixture.restored_application_defaults if self.connection.restored and fixture.restored_application_defaults is not None else fixture.application_defaults
                self.rows = ([] if self.connection.restored else fixture.provider_defaults) + app_defaults
            elif 'SELECT DISTINCT r.rolname' in query:
                self.rows = [('synthetic-worker',)]
            elif 'has_column_privilege' in query:
                self.rows = [(False,)]
            elif 'SELECT bool_and(NOT has_table_privilege' in query:
                self.rows = [(not fixture.worker_can_mutate,)]
            elif 'SELECT bool_and(NOT has_any_column_privilege' in query:
                self.rows = [(not fixture.worker_can_mutate_columns,)]
            elif 'SELECT bool_and(has_table_privilege' in query or 'SELECT bool_and(has_function_privilege' in query:
                self.rows = [(True,)]
            elif 'has_table_privilege' in query or 'has_function_privilege' in query:
                permission = params[-1]
                self.rows = [(permission in ('SELECT', 'EXECUTE') or params[1] == 'public.hosted_sessions'
                              or (params[1] == 'public.hosted_owner_identity' and permission == 'INSERT'),)]
            elif "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY" in query:
                self.rows = [('hosted_snapshot_generations',)]
            elif 'SELECT md5(row_to_json(t)' in query:
                self.rows = [('synthetic-record-digest',)]
            elif 'c.relname,c.relkind,' in query:
                if 'aclexplode' in query:
                    self.rows = [('synthetic-table', 'r', [fixture.restored_grant if self.connection.restored else ['owner', 'owner', 'SELECT', False]], 'id', [])]
                else:
                    self.rows = [('synthetic-table', 'r', '' if self.connection.restored else '{owner=r/owner}', 'id', '')]
            elif "data_classification<>'synthetic'" in query:
                self.rows = [(True, False)]
            elif 'SELECT EXISTS(' in query:
                self.rows = [(self.connection.unexpected and 'FROM pg_class c JOIN pg_namespace' in query,)]
            elif 'SELECT generation_id FROM hosted_snapshot_pointer' in query:
                self.rows = [('synthetic-original',)]
            elif 'UPDATE hosted_snapshot_generations SET published_at' in query:
                raise Immutable()

        def fetchone(self):
            return self.rows.pop(0)

        def fetchall(self):
            result, self.rows = self.rows, []
            return result

        def fetchmany(self, size):
            return self.fetchall()

    class Connection:
        closed = False
        unexpected = False

        def __init__(self, restored):
            self.restored = restored

        def cursor(self):
            return Cursor(self)

        def set_session(self, **kwargs):
            pass

        def rollback(self):
            pass

        def close(self):
            self.closed = True
            events.append('restored connection closed' if self.restored else 'source connection closed')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            # psycopg2 context managers commit/rollback but DO NOT close.
            pass

    def connect(*args, **kwargs):
        result = Connection(kwargs.get('dbname', '').startswith('degiro_recovery_probe_'))
        result.unexpected = fixture.unexpected
        connections.append(result)
        return result

    def process(command, **kwargs):
        if '--version' in command:
            return SimpleNamespace(stdout=b'pg_dump (PostgreSQL) 17.11', stderr=b'', returncode=0)
        events.append('archive command executed')
        for argument in command:
            if argument.startswith('--file='):
                content = fixture.schema_script if '--schema-only' in command else fixture.toc_script if '--list' in command else b'invented-private-archive'
                Path(argument[7:]).write_bytes(content)
            if argument.startswith('--use-list='):
                fixture.restore_list = Path(argument[11:]).read_bytes()
        if any(argument.startswith('--dbname=') for argument in command):
            return SimpleNamespace(stdout=b'', stderr=fixture.restore_stderr,
                                   returncode=1 if fixture.restore_stderr else 0)
        return SimpleNamespace(stdout=b'', stderr=fixture.private_stderr, returncode=0)

    for name in ('pg_dump', 'pg_restore'):
        (tmp_path / name).write_text('synthetic client placeholder')
    environment = {'STAGING_PUBLISHER_DATABASE_URL':
                   'postgresql://owner:secret@ep-synthetic-only.neon.tech/neondb?sslmode=require',
                   'STAGING_EXPECTED_HOST': 'ep-synthetic-only.neon.tech',
                   'STAGING_EXPECTED_DATABASE': 'neondb',
                   'STAGING_BRANCH_ID': 'br-tiny-moon-al8b0u31', 'PG_BIN': str(tmp_path)}
    fixture = SimpleNamespace(environment=environment, connections=connections, events=events,
                              unexpected=False, private_stderr=b'', restore_stderr=b'', schema_script=b'',
                              provider_defaults=[(10, 826, 'cloud_admin', 'public', 'S', 'provider-sequence-acl', 2),
                                                 (11, 826, 'cloud_admin', 'public', 'r', 'provider-table-acl', 7)],
                              application_defaults=[], restore_list=None,
                              restored_application_defaults=None,
                              worker_can_mutate=False,
                              worker_can_mutate_columns=False,
                              restored_grant=['owner', 'owner', 'SELECT', False],
                              toc_script=b'10; 826 10 DEFAULT ACL public DEFAULT PRIVILEGES FOR SEQUENCES cloud_admin\n11; 826 11 DEFAULT ACL public DEFAULT PRIVILEGES FOR TABLES cloud_admin\n20; 0 0 ACL public TABLE hosted_snapshot_generations owner\n')
    monkeypatch.setattr(psycopg2, 'connect', connect)
    monkeypatch.setattr(subprocess, 'run', process)
    return fixture


def test_full_rehearsal_releases_restored_connections_before_database_cleanup(recovery_driver):
    recovery_driver.environment['STAGING_PUBLISHER_DATABASE_URL'] += '&channel_binding=require&application_name=staging%20rehearsal&connect_timeout=5'
    result = rehearse(recovery_driver.environment)
    assert result['state'] == 'application_recovery_passed'
    assert all(connection.closed for connection in recovery_driver.connections)
    assert recovery_driver.events.count('restored connection closed') == 2
    assert recovery_driver.events.index('owned database dropped') > max(
        index for index, event in enumerate(recovery_driver.events) if event == 'restored connection closed')


def test_restore_omits_only_reviewed_provider_default_oids_and_reports_reduced_scope(recovery_driver):
    application_line = b'30; 826 30 DEFAULT ACL public DEFAULT PRIVILEGES FOR TABLES owner\n'
    recovery_driver.application_defaults = [(30, 826, 'owner', 'public', 'r', 'application-acl', 1)]
    recovery_driver.toc_script += application_line
    result = rehearse(recovery_driver.environment)
    assert result['state'] == 'application_recovery_passed'
    assert result['provider_default_acl_entries_not_restored'] == 2
    assert result['provider_default_grants_not_restored'] == 9
    assert result['full_platform_metadata_equal'] is False
    assert result['worker_effective_privileges_verified'] is True
    assert b';10; 826 10 DEFAULT ACL' in recovery_driver.restore_list
    assert b';11; 826 11 DEFAULT ACL' in recovery_driver.restore_list
    assert b'20; 0 0 ACL public TABLE hosted_snapshot_generations owner\n' in recovery_driver.restore_list
    assert application_line in recovery_driver.restore_list


def test_unmapped_provider_default_toc_entry_stops_before_database_creation(recovery_driver):
    recovery_driver.toc_script = recovery_driver.toc_script.replace(b'11; 826 11 DEFAULT ACL', b'11; 1255 11 FUNCTION')
    with pytest.raises(ValueError):
        rehearse(recovery_driver.environment)
    assert 'owned database created' not in recovery_driver.events


def test_application_default_privilege_loss_cannot_pass_recovery(recovery_driver):
    recovery_driver.application_defaults = [(30, 826, 'owner', 'public', 'r', 'application-acl', 1)]
    recovery_driver.restored_application_defaults = []
    recovery_driver.toc_script += b'30; 826 30 DEFAULT ACL public DEFAULT PRIVILEGES FOR TABLES owner\n'
    with pytest.raises(ValueError, match='Recovery comparison failed'):
        rehearse(recovery_driver.environment)
    assert 'owned database dropped' in recovery_driver.events


def test_forbidden_worker_mutation_privilege_stops_recovery_before_archive(recovery_driver):
    recovery_driver.worker_can_mutate = True
    with pytest.raises(ValueError, match='Worker can directly mutate protected state'):
        rehearse(recovery_driver.environment)
    assert 'archive command executed' not in recovery_driver.events
    assert 'owned database created' not in recovery_driver.events


def test_column_only_worker_mutation_privilege_stops_recovery_before_archive(recovery_driver):
    recovery_driver.worker_can_mutate_columns = True
    assert recovery_driver.worker_can_mutate is False
    with pytest.raises(ValueError, match='Worker can directly mutate protected state'):
        rehearse(recovery_driver.environment)
    assert 'archive command executed' not in recovery_driver.events
    assert 'owned database created' not in recovery_driver.events


def test_explicit_default_and_null_relation_acls_compare_equally(recovery_driver):
    assert rehearse(recovery_driver.environment)['state'] == 'application_recovery_passed'


@pytest.mark.parametrize('changed_grant', [
    ['other', 'owner', 'SELECT', False],
    ['owner', 'other', 'SELECT', False],
    ['owner', 'owner', 'UPDATE', False],
    ['owner', 'owner', 'SELECT', True],
])
def test_relation_privilege_drift_fails_comparison(recovery_driver, changed_grant):
    recovery_driver.restored_grant = changed_grant
    with pytest.raises(ValueError, match='Recovery comparison failed'):
        rehearse(recovery_driver.environment)
    assert 'owned database dropped' in recovery_driver.events


def test_unreviewed_application_relations_stop_export_before_any_archive_or_restore(recovery_driver):
    recovery_driver.unexpected = True
    with pytest.raises(ValueError, match='Unexpected application schema or relation kind'):
        rehearse(recovery_driver.environment)
    assert 'archive command executed' not in recovery_driver.events
    assert 'owned database created' not in recovery_driver.events
    assert all(connection.closed for connection in recovery_driver.connections)


@pytest.mark.parametrize('override', ['host=other.example', 'dbname=otherdb',
                                     'hostaddr=127.0.0.1', 'service=other'])
def test_recovery_rejects_libpq_destination_overrides_before_driver_or_archive(recovery_driver, override):
    recovery_driver.environment['STAGING_PUBLISHER_DATABASE_URL'] += '&'+override
    with pytest.raises(ValueError):
        rehearse(recovery_driver.environment)
    assert recovery_driver.connections == []
    assert recovery_driver.events == []


def test_recovery_rejects_ambient_host_address_before_any_connection(recovery_driver, monkeypatch):
    monkeypatch.setenv('PGHOSTADDR', '127.0.0.1')
    with pytest.raises(ValueError):
        rehearse(recovery_driver.environment)
    assert recovery_driver.connections == []
    assert recovery_driver.events == []


def test_recovery_cli_requires_real_postgres_clients_before_connecting(tmp_path):
    environment = {**os.environ, 'STAGING_PUBLISHER_DATABASE_URL':
                   'postgresql://owner:secret@ep-synthetic-only.neon.tech/neondb?sslmode=require',
                   'STAGING_EXPECTED_HOST': 'ep-synthetic-only.neon.tech',
                   'STAGING_EXPECTED_DATABASE': 'neondb',
                   'STAGING_BRANCH_ID': 'br-tiny-moon-al8b0u31',
                   'PG_BIN': str(tmp_path)}
    result = subprocess.run([sys.executable, '-m', 'backend.staging_recovery'],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'Staging recovery rehearsal failed; credentials and database content withheld.' in result.stdout
    assert result.stderr == ''
