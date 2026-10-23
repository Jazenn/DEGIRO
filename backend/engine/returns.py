"""Geometrically linked daily Modified Dietz estimates over canonical daily values.

No transaction classification, FIFO, cash accounting or provider work is repeated.
External amounts reuse the canonical ledger's preserved source decimals and FX.
"""
from decimal import Decimal, localcontext
import pandas as pd
from backend.engine.ledger import exact, eur_rate


def flow_observations(transactions, settings, start, end):
    timezone = settings.get('source_timezone', {})
    if timezone.get('verified') is not True or not timezone.get('evidence') or not timezone.get('name'):
        raise ValueError('external_flow_timezone_unverified')
    local_start = start.tz_convert(timezone['name']).date()
    local_end = end.tz_convert(timezone['name']).date()
    flows = []
    for row in transactions.to_dict('records'):
        if row.get('type') not in ('DEPOSIT', 'WITHDRAWAL') or row.get('is_cash_sweep'):
            continue
        if row.get('normalized_date'):
            date = pd.Timestamp(row['normalized_date']).date()
            # Timing before the selected opening is already represented by B.
            if date < local_start or date > local_end:
                continue
        if not row.get('time') or not row.get('normalized_date') or not row.get('row_hash'):
            raise ValueError('external_flow_timing_unknown')
        try:
            # Same normalized broker wall-time convention as calculate_portfolio.
            at = pd.Timestamp(row['normalized_date'] + ' ' + row['time'])
            if pd.isna(at) or at.tzinfo is not None:
                raise ValueError('external_flow_timing_unknown')
            at = at.tz_localize(timezone['name'], ambiguous='raise', nonexistent='raise').tz_convert('UTC')
        except Exception:
            raise ValueError('external_flow_timing_unknown_or_dst_ambiguous') from None
        rate = eur_rate(row, settings)
        if rate is None:
            raise ValueError('external_flow_dated_fx_unavailable')
        flows.append((at, exact(row, 'amount') * rate, row['row_hash']))
    return flows


def estimated_return(points, transactions, settings):
    result = {'method': 'geometrically_linked_daily_modified_dietz', 'state': 'unavailable',
              'start': points[0]['cutoff'] if points else None,
              'cutoff': points[-1]['cutoff'] if points else None, 'percent': None, 'daily': []}
    if len(points) < 2 or any(point.get('equity_eur') is None or point.get('ledger') is None for point in points):
        return {**result, 'diagnostics': ['missing_daily_valuation_or_flow_coverage']}
    try:
        flows = flow_observations(transactions, settings, pd.Timestamp(points[0]['cutoff']), pd.Timestamp(points[-1]['cutoff']))
    except ValueError as error:
        return {**result, 'diagnostics': [str(error)]}
    with localcontext() as context:
        context.prec = 40
        factor = Decimal(1)
        for first, last in zip(points, points[1:]):
            start, end = pd.Timestamp(first['cutoff']), pd.Timestamp(last['cutoff'])
            if end - start != pd.Timedelta(days=1):
                return {**result, 'diagnostics': ['nonconsecutive_daily_cutoffs']}
            # Start is already included in opening equity; endpoint flows have weight zero.
            interval = [(at, amount, identity) for at, amount, identity in flows if start < at <= end]
            total = sum((amount for _, amount, _ in interval), Decimal(0))
            expected = Decimal(last['ledger']['net_external_contributions_eur']) - Decimal(first['ledger']['net_external_contributions_eur'])
            if total != expected:
                return {**result, 'diagnostics': ['external_flows_do_not_reconcile']}
            weighted = Decimal(0)
            weights = []
            for at, amount, identity in interval:
                remaining = end - at
                seconds = Decimal(remaining.days * 86400 + remaining.seconds) + Decimal(remaining.microseconds) / Decimal(1000000)
                weight = seconds / Decimal(86400)
                weighted += amount * weight
                weights.append({'transaction_id': identity, 'at': at.isoformat(), 'amount_eur': str(amount), 'remaining_interval_weight': str(weight)})
            denominator = Decimal(first['equity_eur']) + weighted
            gain = Decimal(last['equity_eur']) - Decimal(first['equity_eur']) - total
            if denominator <= 0:
                return {**result, 'diagnostics': ['nonpositive_daily_dietz_denominator']}
            daily = gain / denominator
            if daily < -1:
                return {**result, 'diagnostics': ['daily_loss_exceeds_capital']}
            result['daily'].append({'start': first['cutoff'], 'cutoff': last['cutoff'], 'net_gain_eur': str(gain),
                'external_flows_eur': str(total), 'weighted_external_flows_eur': str(weighted),
                'denominator_eur': str(denominator), 'fraction': str(daily), 'flows': weights})
            factor *= 1 + daily
        result.update(state='ready', percent=str((factor - 1) * 100), diagnostics=[])
        return result
