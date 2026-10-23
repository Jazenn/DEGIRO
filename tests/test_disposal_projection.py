from decimal import Decimal, localcontext
from backend.ingestion.account_parser import parse_account_csv
from backend.engine.calculation import calculate_portfolio
from backend.engine.disposal_projection import disposal_projection
from backend.engine.ledger import Lot, Position
import pytest

SETTINGS = {'source_timezone': {'name': 'UTC', 'verified': True, 'evidence': 'synthetic'},
            'cost_history': {'verified': True, 'evidence': 'synthetic'},
            'asset_evidence': {'SYN': {'symbol': 'BTC-EUR', 'kind': 'Cryptocurrency', 'verified': True, 'evidence': 'synthetic'}}}


def model(rows):
    text = 'Date,Time,Product,ISIN,Description,Amount,,Order Id\n' + '\n'.join(rows)
    return calculate_portfolio(parse_account_csv(text), observed_prices={}, settings=SETTINGS,
        ledger_version='synthetic-ledger', settings_version='synthetic-financial', cutoff='2026-01-10T00:00:00Z').to_read_model()


def test_canonical_projection_contains_acquisition_fees_and_explicit_error_bound():
    value = model(['02-01-2026,09:00,Coin,SYN,Buy 1 @ 475 EUR,EUR,-475,b',
                   '02-01-2026,09:01,Coin,SYN,Transaction fee,EUR,-5,b'])
    curve = value['disposal_cost_projections']['SYN']
    assert curve['state'] == 'available'
    assert curve['breakpoints'] == [{'quantity': '0', 'cost_eur': '0'}, {'quantity': '1', 'cost_eur': '480'}]
    assert curve['ledger_version'] == 'synthetic-ledger'
    assert Decimal(curve['absolute_error_bound_eur']) > 0
    assert curve['maximum_hypothetical_disposals'] == '3'


def projected(curve, quantity):
    quantity = Decimal(quantity)
    for left, right in zip(curve['breakpoints'], curve['breakpoints'][1:]):
        if quantity <= Decimal(right['quantity']):
            return Decimal(left['cost_eur']) + (Decimal(right['cost_eur'])-Decimal(left['cost_eur'])) * (quantity-Decimal(left['quantity'])) / (Decimal(right['quantity'])-Decimal(left['quantity']))
    raise AssertionError('Out of range')


@pytest.mark.parametrize('quantity,cost,parts', [('6','1',['1','1','1']), ('7','100',['1','2','1']),
    ('3','480',['0.25','0.75','1']), ('1','520',['0.1','0.2','0.3']), ('1000000000000000000','1',['0.000000000000000001','1','2'])])
def test_outward_bound_contains_actual_canonical_sequential_disposal_costs(quantity, cost, parts):
    base = [f'02-01-2026,09:00,Coin,SYN,Buy {quantity} @ 1 EUR,EUR,-{cost},b']
    before = model(base)
    curve = before['disposal_cost_projections']['SYN']
    assert curve['state'] == 'available'
    rows = list(base)
    prefix = Decimal(0)
    for index, part in enumerate(parts):
        rows.append(f'0{3+index}-01-2026,09:00,Coin,SYN,Sell {part} @ 1 EUR,EUR,1,s{index}')
        after = model(rows)
        with localcontext() as ctx:
            ctx.prec = 80
            actual = Decimal(before['ledger']['positions'][0]['retained_cost_eur']) - Decimal(after['ledger']['positions'][0]['retained_cost_eur'])
            center = projected(curve, prefix+Decimal(part)) - projected(curve, prefix)
            assert abs(actual-center) <= Decimal(curve['absolute_error_bound_eur'])
            prefix += Decimal(part)
        before = after


def test_ill_conditioned_quantity_rounding_counterexample_is_unverified_not_underbounded():
    rows = ['02-01-2026,09:00,Coin,SYN,Buy 0.0000000000000000000000000000000000000001 @ 1 EUR,EUR,-1,b0',
            '03-01-2026,09:00,Coin,SYN,Buy 999999999999999999.999999999999999999999 @ 1 EUR,EUR,-1,b1',
            '04-01-2026,09:00,Coin,SYN,Buy 0.000000000000000000001 @ 1 EUR,EUR,-1000000000000000000,b2',
            '05-01-2026,09:00,Coin,SYN,Buy 0.9999999999999999999999999999999999999999 @ 1 EUR,EUR,-1,b3']
    curve = model(rows)['disposal_cost_projections']['SYN']
    assert curve['state'] == 'unverified'
    assert curve['reason'] == 'projection_range_exceeded'


def test_maximum_segment_count_and_quantity_quantum_keep_exact_endpoints():
    lots = tuple(Lot(str(index), '2026-01-01', Decimal('1e18'), Decimal('1')) for index in range(4096))
    position = Position('SYN','BTC-EUR','Cryptocurrency',Decimal('4096e18'),lots,Decimal(4096),'verified_complete',None,None,None)
    curve = disposal_projection(position, ledger_version='v',financial_settings_version='s',cutoff_eligible=True,ledger_cutoff='2026-01-10T00:00:00Z')
    assert curve['state'] == 'available'
    assert len(curve['breakpoints']) == 4097
    assert curve['breakpoints'][-1]['quantity'] == '4096000000000000000000'
