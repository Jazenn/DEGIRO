"""Independent public BTC/ETH EUR daily series; no private portfolio configuration.

The daily hosted job reuses the observed CoinGecko adapter. It does not rebuild
private Portfolio History or require holdings, source timezone, cost or baseline.
"""
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

from backend.providers.history import fetch_history_input


def fetch_market_coin(symbol, *, now, api_key=None):
    coin_id = {'BTC-EUR': 'bitcoin', 'ETH-EUR': 'ethereum'}[symbol]
    # Public instrument identity only; never inferred from a private broker name.
    config = {'history_sources': {symbol: {'provider': 'coingecko', 'coin_id': coin_id,
              'verified': True, 'evidence': 'CoinGecko market_chart public coin ID, EUR, daily 00:00 UTC'}}}
    data = fetch_history_input(config, now=now, api_key=api_key)
    return {at: quotes[symbol] for at, quotes in data['daily_prices'].items() if symbol in quotes}


def publish_market_history(connection, *, now, api_key=None, require_complete=False):
    from psycopg2.extras import Json
    at = datetime.fromisoformat(now.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('Market history publication requires a timezone')
    midnight = at.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    expected = {(midnight - timedelta(days=n)).isoformat().replace('+00:00', 'Z')
                for n in range(365)}
    results = {}
    for symbol in ['BTC-EUR', 'ETH-EUR']:
        observations, diagnostics = None, []
        try:
            observations = fetch_market_coin(symbol, now=now, api_key=api_key)
            if require_complete and not expected.issubset(observations):
                observations = None
                diagnostics = ['complete_daily_window_required_previous_series_retained']
        except Exception:
            diagnostics = ['provider_request_failed_previous_series_retained']
        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO hosted_crypto_market_history(coin,version,observations,attempted_at,diagnostics)
                VALUES(%s,%s,coalesce(%s::jsonb,'{}'::jsonb),%s,%s)
                ON CONFLICT(coin) DO UPDATE SET version=excluded.version,
                observations=coalesce(%s::jsonb,hosted_crypto_market_history.observations),
                attempted_at=excluded.attempted_at,diagnostics=excluded.diagnostics''',
                (symbol, str(uuid4()), Json(observations) if observations is not None else None, now,
                 Json(diagnostics), Json(observations) if observations is not None else None))
        connection.commit()
        results[symbol] = ({'state': 'retained', 'reason': diagnostics[0]}
                           if observations is None else
                           {'state': 'published', 'completed_days': str(len(expected.intersection(observations)))})
    return results


def main():
    import psycopg2
    with psycopg2.connect(os.environ['DATABASE_URL']) as connection:
        publish_market_history(connection, now=datetime.now(timezone.utc).isoformat(),
                               api_key=os.environ.get('COINGECKO_DEMO_API_KEY'))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Crypto market history job failed; inspect configuration privately.') from None
