"""Observed daily history and EUR attribution through the canonical accounting seam.

No provider calls, interpolation, adjusted prices or legacy cost valuations. Input
adapters must supply dated EUR observations and independently reviewed coverage.
"""
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from backend.engine.calculation import calculate_portfolio


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('History times must include a timezone')
    return result.astimezone(timezone.utc)


def stamp(value):
    return value.isoformat().replace('+00:00', 'Z')


def calendar_months(value, count):
    month = value.year * 12 + value.month - 1 - count
    year, offset = divmod(month, 12)
    return value.replace(year=year, month=offset + 1, day=min(value.day, monthrange(year, offset + 1)[1]))


def calculate_history(transactions, *, settings, daily_prices, asset_coverage,
                      ledger_version, settings_version, now, market_closures=None):
    """Build completed UTC cutoffs only; unknown daily intervals remain unavailable.

    market_closures maps cutoff -> symbol -> explicit exchange-calendar evidence.
    An old official close can be carried only on such declared closed days.
    All result amounts retain Decimal strings from canonical ledger values.
    """
    end = instant(now).replace(hour=0, minute=0, second=0, microsecond=0)
    baseline = settings.get('opening_baseline', {})
    result = {'schema_version': 'observed-history-v1', 'ledger_version': ledger_version,
              'settings_version': settings_version, 'cutoff': stamp(end), 'periods': {}}
    if not daily_prices:
        result['diagnostics'] = ['observed_daily_history_not_supplied']
        return result
    if not baseline.get('verified') or not baseline.get('evidence') or not baseline.get('at'):
        result['diagnostics'] = ['verified_opening_baseline_required']
        return result
    start = instant(baseline['at'])
    # A non-midnight baseline cannot invent that day's opening valuation.
    if start != start.replace(hour=0, minute=0, second=0, microsecond=0):
        start = (start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if start > end:
        result['diagnostics'] = ['completed_opening_cutoff_unavailable']
        return result
    points = []
    day = start
    while day <= end:
        cutoff = stamp(day)
        quotes = daily_prices.get(cutoff, {})
        diagnostics = []
        try:
            model = calculate_portfolio(transactions, observed_prices=quotes, settings=settings,
                ledger_version=ledger_version, settings_version=settings_version, cutoff=cutoff).to_read_model()
            ledger = model['ledger']
            if ledger['equity_eur'] is None or ledger['net_gain_eur'] is None or ledger['attributed_gain_eur'] is None:
                diagnostics.extend(ledger['diagnostics'] or ['incomplete_accounting_coverage'])
            for position in ledger['positions']:
                symbol = position['symbol']
                if position['asset_kind'].lower() not in ('crypto', 'cryptocurrency'):
                    proof = asset_coverage.get(symbol, {})
                    if proof.get('corporate_actions_reconciled') is not True or not proof.get('evidence'):
                        diagnostics.append(f'corporate_actions_unresolved:{symbol}')
                    if proof.get('official_close_verified') is not True:
                        diagnostics.append(f'official_close_unverified:{symbol}')
                if Decimal(position['quantity']) == 0:
                    continue
                quote = quotes.get(symbol)
                if quote is None:
                    diagnostics.append(f'missing_observed_price:{symbol}')
                    continue
                observation = instant(quote.observed_at)
                if position['asset_kind'].lower() in ('crypto', 'cryptocurrency') and observation != day:
                    diagnostics.append(f'crypto_daily_close_missing:{symbol}')
                if observation < day - timedelta(days=1) and not (market_closures or {}).get(cutoff, {}).get(symbol):
                    diagnostics.append(f'unexpected_price_gap:{symbol}')
            point = {'cutoff': cutoff, 'equity_eur': None if diagnostics else ledger['equity_eur'],
                     'ledger': ledger if not diagnostics else None, 'diagnostics': diagnostics,
                     'observed_prices': model['observed_prices']}
        except ValueError as error:
            point = {'cutoff': cutoff, 'equity_eur': None, 'ledger': None,
                     'diagnostics': [str(error)], 'observed_prices': {}}
        points.append(point)
        day += timedelta(days=1)
    requested = {'ALL': start, 'YTD': end.replace(month=1, day=1), '1Y': calendar_months(end, 12),
                 '3M': calendar_months(end, 3), '1M': calendar_months(end, 1), '1W': end - timedelta(days=7)}
    for name, requested_start in requested.items():
        opening = max(start, requested_start)
        selected = [point for point in points if instant(point['cutoff']) >= opening]
        period = {'start': stamp(opening), 'end': stamp(end), 'requested_start': stamp(requested_start),
                  'shorter_coverage': opening > requested_start, 'points': selected, 'state': 'unavailable',
                  'diagnostics': sorted({message for point in selected for message in point['diagnostics']})}
        if len(selected) >= 2 and all(point['ledger'] is not None for point in selected):
            first, last = selected[0]['ledger'], selected[-1]['ledger']
            delta = lambda key: Decimal(last[key]) - Decimal(first[key])
            by_id = lambda ledger: {position['broker_asset_id']: position for position in ledger['positions']}
            old, new = by_id(first), by_id(last)
            assets = []
            for asset in sorted(old.keys() | new.keys()):
                before, after = old.get(asset, {}), new.get(asset, {})
                change = lambda key: Decimal(after.get(key, '0')) - Decimal(before.get(key, '0'))
                assets.append({'broker_asset_id': asset, 'symbol': after.get('symbol', before.get('symbol')),
                    'retained_gain_change_eur': str(change('held_gain_eur')),
                    'realized_gain_change_eur': str(change('realized_gain_eur'))})
            held = sum((Decimal(asset['retained_gain_change_eur']) for asset in assets), Decimal(0))
            realized = sum((Decimal(asset['realized_gain_change_eur']) for asset in assets), Decimal(0))
            gain = delta('equity_eur') - delta('net_external_contributions_eur')
            if held + realized + delta('net_income_eur') - delta('portfolio_costs_eur') == gain:
                period.update(state='ready', assets=assets, attribution={
                    'retained_gain_change_eur': str(held), 'realized_gain_change_eur': str(realized),
                    'net_income_eur': str(delta('net_income_eur')), 'portfolio_costs_eur': str(delta('portfolio_costs_eur')),
                    'net_external_flows_eur': str(delta('net_external_contributions_eur')), 'net_gain_eur': str(gain)})
            else:
                period['diagnostics'].append('equity_bridge_does_not_reconcile')
        elif not period['diagnostics']:
            period['diagnostics'].append('two_observed_endpoints_required')
        result['periods'][name] = period
    return result
