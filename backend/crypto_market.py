"""Independent public BTC/ETH EUR daily series; no private portfolio configuration.

The daily hosted job reuses the observed CoinGecko adapter. It does not rebuild
private Portfolio History or require holdings, source timezone, cost or baseline.
"""
from datetime import datetime, timedelta, timezone
import os
from decimal import Decimal
import re
from uuid import uuid4

from backend.providers.history import fetch_history_input


def fetch_market_coin(symbol, *, now, api_key=None):
    coin_id = {'BTC-EUR': 'bitcoin', 'ETH-EUR': 'ethereum'}[symbol]
    # Public instrument identity only; never inferred from a private broker name.
    config = {'history_sources': {symbol: {'provider': 'coingecko', 'coin_id': coin_id,
              'verified': True, 'evidence': 'CoinGecko market_chart public coin ID, EUR, daily 00:00 UTC'}}}
    data = fetch_history_input(config, now=now, api_key=api_key)
    return {at: quotes[symbol] for at, quotes in data['daily_prices'].items() if symbol in quotes}


def prepare_market_summary(observations, *, coin, version, now, prepared_at=None):
    """Trusted publisher prepares only fully validated 365-day public windows."""
    stamp = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$', re.ASCII)
    def parsed(value):
        if not isinstance(value, str) or not stamp.fullmatch(value):
            raise ValueError('invalid_timestamp')
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    try:
        current = parsed(prepared_at or now)
        end = parsed(now).replace(hour=0, minute=0, second=0, microsecond=0)
        if not isinstance(observations, dict) or len(observations) > 400:
            return None
        rows = {}
        for key, row in observations.items():
            at = parsed(key)
            if at != at.replace(hour=0, minute=0, second=0, microsecond=0) or not end-timedelta(days=365) < at <= end:
                continue
            price = row['price_eur']
            if (not isinstance(price, str) or len(price) > 256 or not re.fullmatch(r'\d+(?:\.\d+)?', price, re.ASCII)
                    or not Decimal(price).is_finite() or Decimal(price) <= 0
                    or row['currency'] != 'EUR' or row['adjustment_basis'] != 'unadjusted'
                    or parsed(row['observed_at']) != at or not at <= parsed(row['retrieved_at']) <= current
                    or not isinstance(row['provider'], str) or not row['provider'] or len(row['provider']) > 200):
                return None
            if at in rows and (rows[at]['price_eur'], rows[at]['provider']) != (price, row['provider']):
                return None
            rows[at] = row
        ordered = [rows[end-timedelta(days=n)] for n in range(364, -1, -1)]
        providers = {row['provider'] for row in ordered}
        if len(providers) != 1:
            return None
        return {'schema': 'prepared-crypto-market-v1', 'coin': coin, 'version': version,
                'cutoff': end.isoformat().replace('+00:00', 'Z'), 'prepared_at': prepared_at or now,
                'required_days': '365', 'available_days': '365', 'provider': providers.pop(),
                'currency': 'EUR', 'adjustment_basis': 'unadjusted',
                'sorted_prices': sorted([row['price_eur'] for row in ordered], key=Decimal),
                'context_prices': [row['price_eur'] for row in ordered[-90:]],
                'context_retrieved_at': [row['retrieved_at'] for row in ordered[-90:]]}
    except (ValueError, KeyError, TypeError, ArithmeticError):
        return None


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
        version = str(uuid4())
        summary = prepare_market_summary(observations, coin=symbol, version=version, now=now,
                                         prepared_at=datetime.now(timezone.utc).isoformat())
        if require_complete and observations is not None and summary is None:
            observations = None
            diagnostics = ['prepared_market_validation_failed_previous_series_retained']
        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO hosted_crypto_market_history(coin,version,observations,attempted_at,diagnostics,prepared_summary)
                VALUES(%s,%s,coalesce(%s::jsonb,'{}'::jsonb),%s,%s,%s)
                ON CONFLICT(coin) DO UPDATE SET
                observations=coalesce(%s::jsonb,hosted_crypto_market_history.observations),
                version=CASE WHEN %s::jsonb IS NULL THEN hosted_crypto_market_history.version ELSE excluded.version END,
                prepared_summary=CASE WHEN %s::boolean THEN hosted_crypto_market_history.prepared_summary ELSE excluded.prepared_summary END,
                attempted_at=excluded.attempted_at,diagnostics=excluded.diagnostics''',
                (symbol, version, Json(observations) if observations is not None else None, now,
                 Json(diagnostics), Json(summary) if summary is not None else None,
                 Json(observations) if observations is not None else None,
                 Json(observations) if observations is not None else None, observations is None))
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
