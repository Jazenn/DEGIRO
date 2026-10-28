"""Validate the effective libpq destination before any staging connection."""
import os
from urllib.parse import parse_qsl, unquote, urlsplit
from psycopg2.extensions import parse_dsn


def checked_staging_url(url, expected_host, expected_database):
    parts = urlsplit(url)
    options = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    allowed = {'sslmode', 'channel_binding', 'connect_timeout', 'application_name'}
    if (not expected_host or not expected_database
            or any(os.environ.get(key) for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'))
            or parts.scheme not in ('postgres', 'postgresql')
            or not parts.hostname or parts.hostname != expected_host
            or '-pooler' in parts.hostname or parts.fragment
            or unquote(parts.path.lstrip('/')) != expected_database
            or any(key not in allowed for key, _ in options)
            or len({key for key, _ in options}) != len(options)):
        raise ValueError('Unapproved staging connection destination')
    # libpq URI query parameters can override authority/path fields. Reject all
    # destination/service overrides above, then independently inspect libpq's
    # effective interpretation rather than relying on URL parsing alone.
    effective = parse_dsn(url)
    if (effective.get('host') != expected_host
            or effective.get('dbname') != expected_database
            or any(key in effective for key in ('hostaddr', 'service', 'servicefile'))
            or effective.get('sslmode') not in ('require', 'verify-ca', 'verify-full')):
        raise ValueError('Unapproved effective staging destination')
    return url
