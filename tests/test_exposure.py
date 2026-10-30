from backend.exposure import build_exposure
from backend.exposure_sources import parse_vanguard_holdings
import pytest


def fund(holdings, **changes):
    return {'as_of': '2026-09-30', 'source_url': 'https://provider.example/fund',
            'retrieved_at': '2026-10-23T10:00:00Z', 'provider': 'Synthetic provider',
            'identifier_namespace': 'ISIN', 'weight_basis': 'fund_net_assets',
            'country_basis': 'synthetic-issuer-domicile', 'sector_taxonomy': 'synthetic-classification',
            'complete': False, 'holdings': holdings, **changes}


def holding(identifier, weight, country='US', sector='Technology'):
    return {'security_id': identifier, 'name': 'Synthetic ' + identifier,
            'weight_pct': weight, 'country': country, 'sector': sector}


def test_partial_fund_coverage_is_not_normalized_to_a_complete_portfolio():
    model = {'ledger': {'market_value_eur': '1000', 'positions': [
        {'broker_asset_id': 'FUND-A', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '600'},
        {'broker_asset_id': 'FUND-B', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '400'}]}}
    exposure = build_exposure(model, {'FUND-A': fund([holding('A', '50')])})
    assert exposure['covered_portfolio_fraction'] == '0.30'
    assert exposure['countries'] == {'US': '30.0'}
    assert exposure['funds'][0]['covered_fund_fraction'] == '0.5'
    assert exposure['funds'][1]['state'] == 'unavailable'


def test_compatible_complete_holdings_have_hand_checked_overlap_but_dates_and_ids_block_claims():
    model = {'ledger': {'market_value_eur': '1000', 'positions': [
        {'broker_asset_id': 'FUND-A', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '500'},
        {'broker_asset_id': 'FUND-B', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '500'}]}}
    a = fund([holding('X', '60'), holding('Y', '40')], complete=True)
    b = fund([holding('X', '25'), holding('Z', '75')], complete=True)
    overlap = build_exposure(model, {'FUND-A': a, 'FUND-B': b})['overlap'][0]
    assert overlap['observed_overlap_pct'] == '25'
    assert overlap['state'] == 'complete'
    b['as_of'] = '2026-09-29'
    assert build_exposure(model, {'FUND-A': a, 'FUND-B': b})['overlap'][0]['observed_overlap_pct'] is None
    b['as_of'] = '2026-09-30'
    b['holdings'][0]['security_id'] = None
    assert build_exposure(model, {'FUND-A': a, 'FUND-B': b})['overlap'][0]['state'] == 'unavailable'


def test_partial_compatible_overlap_is_only_an_observed_lower_bound():
    model = {'ledger': {'market_value_eur': '1000', 'positions': [
        {'broker_asset_id': 'A', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '500'},
        {'broker_asset_id': 'B', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '500'}]}}
    overlap = build_exposure(model, {'A': fund([holding('X', '30')]),
                                     'B': fund([holding('X', '20')])})['overlap'][0]
    assert overlap['observed_overlap_pct'] == '20'
    assert overlap['state'] == 'partial'


def test_matching_provider_reported_scopes_do_not_establish_compatible_fund_weights():
    model = {'ledger': {'market_value_eur': '1000', 'positions': [
        {'broker_asset_id': 'A', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '500'},
        {'broker_asset_id': 'B', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '500'}]}}
    sources = {identifier: fund([holding('X', '100')], complete=True,
                               weight_basis='provider_reported_market_value')
               for identifier in ('A', 'B')}
    overlap = build_exposure(model, sources)['overlap'][0]
    assert overlap['state'] == 'unavailable'
    assert overlap['observed_overlap_pct'] is None


def test_dated_provider_table_remains_partial_and_unknown_ids_never_become_names():
    html = '''<h3>Holdings details</h3><p>As at 30 Sept 2026</p><table>
    <tr><th>Holding name</th><th>% of market value</th><th>Sector</th><th>Region</th></tr>
    <tr><td>Synthetic issuer</td><td>10.5%</td><td>Technology</td><td>US</td></tr></table>'''
    data = parse_vanguard_holdings(html, 'https://www.vanguard.co.uk/professional/fund', '2026-10-23T10:00:00Z')
    assert data['as_of'] == '2026-09-30'
    assert data['holdings'][0]['weight_pct'] == '10.5'
    assert data['holdings'][0]['security_id'] is None
    assert data['weight_basis'] == 'provider_reported_market_value'
    assert data['complete'] is False


@pytest.mark.parametrize('change', [
    {'holdings': [holding('A', '60'), holding('B', '60')]},
    {'complete': True, 'holdings': [holding('A', '99')]},
    {'holdings': [holding('A', '-1')]},
    {'as_of': '2026-02-30'},
    {'retrieved_at': '2026-09-29T00:00:00Z'},
    {'holdings': [holding('A', '50'), holding('A', '50')]},
])
def test_invalid_weights_dates_and_duplicate_ids_never_produce_claims(change):
    model = {'ledger': {'market_value_eur': '100', 'positions': [
        {'broker_asset_id': 'A', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '100'}]}}
    with pytest.raises(ValueError):
        build_exposure(model, {'A': {**fund([holding('A', '100')]), **change}})


def test_closed_funds_do_not_appear_as_current_exposure_or_overlap():
    model = {'ledger': {'market_value_eur': '100', 'positions': [
        {'broker_asset_id': 'HELD', 'quantity': '1', 'asset_kind': 'ETF', 'market_value_eur': '100'},
        {'broker_asset_id': 'SOLD', 'quantity': '0', 'asset_kind': 'ETF', 'market_value_eur': '0'}]}}
    result = build_exposure(model, {})
    assert [row['fund_id'] for row in result['funds']] == ['HELD']
    assert result['overlap'] == []
