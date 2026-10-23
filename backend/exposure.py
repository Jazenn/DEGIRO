"""Dated ETF look-through with explicit coverage; never infer missing holdings."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations
from urllib.parse import urlparse


def number(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid nonnegative exposure value')
    return result


def validate_fund(fund):
    date.fromisoformat(fund['as_of'])
    retrieved = datetime.fromisoformat(fund['retrieved_at'].replace('Z', '+00:00'))
    if retrieved.tzinfo is None or retrieved.date() < date.fromisoformat(fund['as_of']):
        raise ValueError('Invalid exposure source timestamps')
    source = urlparse(fund['source_url'])
    if source.scheme != 'https' or not source.hostname or source.username or source.password or not isinstance(fund.get('provider'), str) or not fund.get('provider'):
        raise ValueError('Exposure source provenance required')
    if fund.get('weight_basis') not in ('fund_net_assets', 'provider_reported_market_value') or not isinstance(fund.get('complete'), bool):
        raise ValueError('Unsupported exposure weight basis')
    weights = [number(row['weight_pct']) for row in fund['holdings']]
    if not weights or sum(weights) > 100 or any(weight > 100 for weight in weights):
        raise ValueError('Invalid exposure weights')
    if fund['complete'] and sum(weights) != 100:
        raise ValueError('Complete fund weights must total 100%; retain residual as unknown')
    for row in fund['holdings']:
        if not isinstance(row.get('name'), str) or not row.get('name') or not isinstance(row['weight_pct'], str):
            raise ValueError('Holding name required')
        if any(row.get(key) is not None and not isinstance(row.get(key), str) for key in ('security_id', 'country', 'sector')):
            raise ValueError('Holding identifiers and classifications must be strings')
    if any(fund.get(key) is not None and not isinstance(fund.get(key), str) for key in ('identifier_namespace', 'country_basis', 'sector_taxonomy')):
        raise ValueError('Source namespaces must be strings')
    ids = [row.get('security_id') for row in fund['holdings'] if row.get('security_id')]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate security identifiers require aggregation/review')
    return sum(weights) / 100


def build_exposure(model, sources):
    """Weights remain percentages of original funds/portfolio, never renormalized."""
    positions = [row for row in model['ledger']['positions'] if number(row['quantity']) > 0]
    total = model['ledger']['market_value_eur']
    total = number(total) if total is not None else None
    if total is not None and (any(row['market_value_eur'] is None for row in positions)
                              or sum((number(row['market_value_eur']) for row in positions), Decimal(0)) != total):
        raise ValueError('Exposure denominator must reconcile with every holding market value')
    countries, sectors = defaultdict(Decimal), defaultdict(Decimal)
    relevant = [sources[row['broker_asset_id']] for row in positions
                if row['asset_kind'] == 'ETF' and row['broker_asset_id'] in sources
                and sources[row['broker_asset_id']].get('weight_basis') == 'fund_net_assets']
    country_bases = {source.get('country_basis') for source in relevant}
    sector_bases = {source.get('sector_taxonomy') for source in relevant}
    aggregate_countries = len(country_bases) == 1 and bool(next(iter(country_bases)))
    aggregate_sectors = len(sector_bases) == 1 and bool(next(iter(sector_bases)))
    funds, accepted = [], {}
    covered = Decimal(0)
    for position in positions:
        if position['asset_kind'] != 'ETF':
            continue
        identifier = position['broker_asset_id']
        source = sources.get(identifier)
        entry = {'fund_id': identifier, 'state': 'unavailable', 'limitations': ['No dated fund holdings source available.']}
        if source:
            fraction = validate_fund(source)
            value = position['market_value_eur']
            value = number(value) if value is not None else None
            portfolio_fraction = value / total if value is not None and total and source['weight_basis'] == 'fund_net_assets' else None
            source_fields = {key: source.get(key) for key in ('as_of', 'retrieved_at', 'source_url', 'provider', 'identifier_namespace', 'weight_basis', 'complete', 'country_basis', 'sector_taxonomy')}
            source_fields['holdings'] = [{key: row.get(key) for key in ('name', 'security_id', 'weight_pct', 'country', 'sector')} for row in source['holdings']]
            entry = {**source_fields, 'fund_id': identifier, 'state': 'covered' if source['complete'] else 'partial',
                     'covered_fund_fraction': str(fraction) if source['weight_basis'] == 'fund_net_assets' else None,
                     'covered_reported_fraction': str(fraction),
                     'portfolio_fraction': str(portfolio_fraction) if portfolio_fraction is not None else None,
                     'top_ten_weight_pct': str(sum(sorted((number(r['weight_pct']) for r in source['holdings']), reverse=True)[:10])),
                     'concentration_basis': 'exact' if source['complete'] else 'observed_lower_bound',
                     'limitations': [] if source['complete'] else ['Partial holdings; unreported exposure is unknown.']}
            if portfolio_fraction is None:
                entry['limitations'].append('Portfolio coverage unavailable without complete market values and verified fund net-asset denominator.')
            entry['countries'] = {key: str(sum((number(row['weight_pct']) for row in source['holdings'] if row.get('country') == key), Decimal(0))) for key in sorted({row['country'] for row in source['holdings'] if row.get('country')})}
            entry['sectors'] = {key: str(sum((number(row['weight_pct']) for row in source['holdings'] if row.get('sector') == key), Decimal(0))) for key in sorted({row['sector'] for row in source['holdings'] if row.get('sector')})}
            if portfolio_fraction is not None:
                covered += portfolio_fraction * fraction
                for row in source['holdings']:
                    weight = portfolio_fraction * number(row['weight_pct'])
                    if row.get('country') and aggregate_countries:
                        countries[row['country']] += weight
                    if row.get('sector') and aggregate_sectors:
                        sectors[row['sector']] += weight
            accepted[identifier] = source
        funds.append(entry)
    overlaps = []
    for left, right in combinations(funds, 2):
        a, b = accepted.get(left['fund_id']), accepted.get(right['fund_id'])
        item = {'fund_a': left['fund_id'], 'fund_b': right['fund_id'], 'state': 'unavailable',
                'observed_overlap_pct': None, 'reason': 'Missing or incompatible dates, identifiers or weight basis.'}
        if a and b and a['as_of'] == b['as_of'] and a['weight_basis'] == b['weight_basis'] and a.get('identifier_namespace') \
                and a.get('identifier_namespace') == b.get('identifier_namespace') \
                and all(row.get('security_id') for row in a['holdings'] + b['holdings']):
            aw = {row['security_id']: number(row['weight_pct']) for row in a['holdings']}
            bw = {row['security_id']: number(row['weight_pct']) for row in b['holdings']}
            overlap = sum((min(weight, bw.get(key, Decimal(0))) for key, weight in aw.items()), Decimal(0))
            complete = a['complete'] and b['complete']
            item.update(state='complete' if complete else 'partial', observed_overlap_pct=str(overlap),
                        as_of=a['as_of'], reason='Sum of minimum fund weights for matching identifiers.' if complete
                        else 'Observed lower bound only; missing holdings may overlap too.')
        overlaps.append(item)
    return {'schema_version': 'etf-exposure-v1', 'denominator': 'invested_asset_market_value_excluding_cash',
            'covered_portfolio_fraction': str(covered) if total else None,
            'country_classification': next(iter(country_bases)) if aggregate_countries else None,
            'sector_classification': next(iter(sector_bases)) if aggregate_sectors else None,
            'countries': {key: str(value) for key, value in sorted(countries.items())},
            'sectors': {key: str(value) for key, value in sorted(sectors.items())},
            'funds': funds, 'overlap': overlaps,
            'limitations': ['Country and sector totals are observed percentages of all invested assets, excluding cash; unreported fractions remain unknown.',
                            'Cross-fund country/sector totals require compatible documented classification methods; otherwise only fund-level reported breakdowns are shown.']}
