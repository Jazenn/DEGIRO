"""Canonical bounded remaining-inventory cost projection, not execution accounting.

Projection consumers interpolate declared cumulative output; FIFO order and all
acquisition fees have already been resolved by the authoritative Python ledger.
"""
from decimal import Decimal, localcontext, ROUND_CEILING


def disposal_projection(position, *, ledger_version, financial_settings_version, cutoff_eligible, ledger_cutoff):
    base = {'schema_version': 'bounded-disposal-curve-v1', 'broker_asset_id': position.broker_asset_id,
            'ledger_version': ledger_version, 'financial_settings_version': financial_settings_version,
            'calculation_version': 'decimal-accounting-v1', 'cost_coverage': position.cost_coverage,
            'quantity_limit': str(position.quantity), 'maximum_hypothetical_disposals': '3',
            'precision_policy': 'canonical40-consumer80-outward-bound-v1', 'state': 'unverified',
            'cutoff_eligible': cutoff_eligible, 'ledger_cutoff': ledger_cutoff,
            'breakpoints': [], 'absolute_error_bound_eur': None}
    if not cutoff_eligible or position.cost_coverage != 'verified_complete':
        return {**base, 'reason': 'complete_cost_and_cutoff_evidence_required'}
    if len(position.lots) > 4096:
        return {**base, 'reason': 'projection_range_exceeded'}
    with localcontext() as ctx:
        ctx.prec = 80
        def supported(value, positive=False):
            return (value is not None and value.is_finite() and value >= 0 and (not positive or value > 0)
                    and value <= Decimal('1e18') and value.as_tuple().exponent >= (-18 if positive else -40)
                    and len(value.as_tuple().digits) <= 40)
        if any(not supported(lot.quantity, True) or not supported(lot.cost_eur) for lot in position.lots):
            return {**base, 'reason': 'projection_range_exceeded'}
        quantity, cost = Decimal(0), Decimal(0)
        points = [{'quantity': '0', 'cost_eur': '0'}]
        for lot in position.lots:
            quantity += lot.quantity
            cost += lot.cost_eur
            points.append({'quantity': format(quantity, 'f'), 'cost_eur': format(cost, 'f')})
        if quantity != position.quantity or cost != position.retained_cost_eur:
            return {**base, 'reason': 'projection_endpoints_require_exact_reconciliation'}
        # u40=5e-40 bounds one normal 40-digit half-even operation. For at most
        # three removals/segment: <=40u40*C covers multiply/divide/residual error;
        # <=2Nu40*C covers accumulation. 100(N+1) also dominates 80-digit
        # interpolation error. Quantity scale<=18, N<=4096 and q<=1e18 imply
        # every positive sum/residual uses <1e40 integer quantum units, so ALL
        # canonical quantity operations are exact (no steep-slope amplification).
        # Cost endpoint sums use <63 significant digits; operations stay normal.
        ctx.rounding = ROUND_CEILING
        bound = Decimal(100) * (len(position.lots) + 1) * Decimal('5e-40') * max(Decimal(1), cost)
        return {**base, 'state': 'available', 'breakpoints': points,
                'absolute_error_bound_eur': format(bound, 'f'), 'reason': None}
