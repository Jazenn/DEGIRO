"""Bounded public crypto history adapter; reviewed symbol mapping stays server-side.

Only exact observed 00:00 UTC samples are usable. CoinGecko's trailing live sample
is discarded. The Demo 365-day limit is not a complete all-time history source.
"""
import json
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal


def coingecko_observations(payload, *, symbol, retrieved_at, now):
    end = datetime.fromisoformat(now.replace('Z', '+00:00')).astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = {}
    for timestamp_ms, value in payload.get('prices', []):
        timestamp_ms = Decimal(str(timestamp_ms))
        if timestamp_ms % 86400000:
            continue
        observed = datetime.fromtimestamp(int(timestamp_ms) / 1000, timezone.utc)
        price = Decimal(str(value))
        if observed > end or not price.is_finite() or price <= 0:
            continue
        at = observed.isoformat().replace('+00:00', 'Z')
        quote = {'price_eur': str(price), 'observed_at': at,
                 'provider': 'CoinGecko Demo market_chart EUR daily', 'currency': 'EUR',
                 'adjustment_basis': 'unadjusted', 'retrieved_at': retrieved_at}
        if at in rows and rows[at][symbol] != quote:
            raise ValueError('conflicting_daily_observations')
        rows[at] = {symbol: quote}
    return rows


def fetch_history_input(settings, *, now, api_key=None):
    result = {'daily_prices': {}, 'asset_coverage': {}, 'market_closures': {}}
    sources = settings.get('history_sources', {})
    if len(sources) > 2:
        raise ValueError('history_provider_call_limit')
    for symbol, source in sources.items():
        if (source.get('provider') != 'coingecko' or source.get('coin_id') not in ('bitcoin', 'ethereum')
                or source.get('verified') is not True or not source.get('evidence')):
            raise ValueError('history_source_mapping_requires_review')
        url = f"https://api.coingecko.com/api/v3/coins/{source['coin_id']}/market_chart?vs_currency=eur&days=365&interval=daily&precision=full"
        headers = {'User-Agent': 'DEGIRO-observed-history/1'}
        if api_key:
            headers['x-cg-demo-api-key'] = api_key
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as response:
            payload = json.load(response, parse_float=Decimal)
        retrieved = datetime.now(timezone.utc).isoformat()
        for at, quotes in coingecko_observations(payload, symbol=symbol, retrieved_at=retrieved, now=now).items():
            result['daily_prices'].setdefault(at, {}).update(quotes)
    return result
