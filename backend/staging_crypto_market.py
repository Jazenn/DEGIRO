"""Publish public daily history only to the approved synthetic staging database.

Uses the existing producer and no private calculation configuration. Never prints
provider exception text, connection strings, API keys or price observations.
"""
from datetime import datetime, timezone
import json
import os

from backend.crypto_market import publish_market_history
from backend.staging_connection import checked_staging_url


def main():
    import psycopg2
    try:
        if (os.environ.get('STAGING_CRYPTO_HISTORY_APPROVED') != 'synthetic-staging-only'
                or not os.environ.get('COINGECKO_DEMO_API_KEY', '').strip()):
            raise ValueError('Missing explicit staging approval or Demo key')
        url = checked_staging_url(os.environ['STAGING_PUBLISHER_DATABASE_URL'],
                                  os.environ.get('STAGING_EXPECTED_HOST'),
                                  os.environ.get('STAGING_EXPECTED_DATABASE'))
    except Exception:
        print(json.dumps({'state': 'failed', 'reason': 'destination_or_key_rejected'}))
        return 1
    try:
        with psycopg2.connect(url, connect_timeout=15) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*),bool_and(data_classification='synthetic') FROM hosted_snapshot_generations")
                count, synthetic = cursor.fetchone()
                if not count or synthetic is not True:
                    raise ValueError('Expected existing synthetic-only staging')
            results = publish_market_history(connection, now=datetime.now(timezone.utc).isoformat(),
                                             api_key=os.environ['COINGECKO_DEMO_API_KEY'],
                                             require_complete=True)
        ready = all(result['state'] == 'published' for result in results.values())
        print(json.dumps({'state': 'published' if ready else 'failed', 'coins': results}))
        return 0 if ready else 1
    except Exception:
        print(json.dumps({'state': 'failed', 'reason': 'staging_market_history_unavailable'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
