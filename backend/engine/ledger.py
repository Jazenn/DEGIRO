"""Decimal accounting read model. No network, persistence or current tariffs."""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import re
import pandas as pd
from backend.engine.cash import sort_transactions_chronologically
from backend.engine.source_timing import source_timezone_policy

ZERO = Decimal(0)


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Non-finite ledger amount')
    return result


def source_number(value):
    text = str(value).strip().replace(' ', '')
    if text.rfind(',') > text.rfind('.'):
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '')
    return number(text)


def exact(row, field):
    """Read preserved broker text, never round-trip money through binary floats."""
    if field in (row.get('exact_fields') or {}):
        return number(row['exact_fields'][field])
    src = row.get('source_record') or {}
    kind = row.get('source_format')
    if kind == 'account':
        if field == 'quantity':
            match = re.search(r'(?:Koop|Verkoop|Buy|Sell)\s+([0-9.,]+)', row['description'], re.I)
            return source_number(match[1]) if match else None
        if field == 'amount':
            for key in ('mutatie', 'change', 'amount'):
                if key in src:
                    keys = list(src)
                    value = src[key]
                    if str(value).isalpha():
                        value = src[keys[keys.index(key)+1]]
                    return source_number(value) if value else ZERO
    if kind == 'transactions':
        names = {'quantity': ('aantal', 'quantity'), 'amount': ('waarde eur', 'value eur', 'waarde', 'value', 'lokale waarde', 'waarde in lokale valuta', 'local value', 'value in local currency')}
        if row['type'] == 'FEE':
            names['amount'] = ('transactiekosten en/of kosten van derden eur', 'transaction costs', 'fee')
        for key in names.get(field, ()):
            if src.get(key):
                val = source_number(src[key])
                if field == 'amount':
                    return -abs(val) if row['type'] in ('BUY', 'FEE') else abs(val)
                return abs(val)
        if field == 'quantity':
            for key in ('koers', 'price'):
                if src.get(key):
                    return abs(exact(row, 'amount') / source_number(src[key]))
    val = row.get(field)
    return None if val is None or pd.isna(val) else abs(number(val)) if field == 'quantity' else number(val)


def eur_rate(row, settings):
    if row.get('amount_currency') == 'EUR':
        return Decimal(1)
    evidence = settings.get('fx_evidence', {}).get(row['row_hash'], {})
    if (evidence.get('verified') is True and evidence.get('provider')
            and evidence.get('currency') == row.get('amount_currency')
            and evidence.get('date') == row.get('normalized_date')):
        rate = number(evidence['eur_per_unit'])
        if rate > 0:
            return rate
    return None


@dataclass(frozen=True)
class Lot:
    transaction_id: str
    acquired_at: str
    quantity: Decimal
    cost_eur: Decimal | None


@dataclass(frozen=True)
class Position:
    broker_asset_id: str
    symbol: str | None
    asset_kind: str
    quantity: Decimal
    lots: tuple[Lot, ...]
    retained_cost_eur: Decimal | None
    cost_coverage: str
    market_value_eur: Decimal | None
    held_gain_eur: Decimal | None
    realized_gain_eur: Decimal | None


@dataclass(frozen=True)
class Charge:
    transaction_id: str
    date: str
    category: str
    amount_eur: Decimal
    allocation: str


@dataclass(frozen=True)
class Ledger:
    schema_version: str
    positions: tuple[Position, ...]
    charges: tuple[Charge, ...]
    cash_balance_eur: Decimal | None
    net_external_contributions_eur: Decimal
    market_value_eur: Decimal | None
    equity_eur: Decimal | None
    net_gain_eur: Decimal | None
    attributed_gain_eur: Decimal | None
    gross_income_eur: Decimal
    withholding_eur: Decimal
    net_income_eur: Decimal
    portfolio_costs_eur: Decimal
    diagnostics: tuple[str, ...]
    disposals: tuple[dict, ...] = ()


def calculate_ledger(frame, prices, settings, cutoff, *, cutoff_eligible):
    with localcontext() as ctx:
        ctx.prec = 40
        return _calculate(frame, prices, settings, cutoff, cutoff_eligible)


def _calculate(frame, prices, settings, cutoff, cutoff_eligible):
    diagnostics = []
    timing = source_timezone_policy(settings)
    if timing and timing['status'] == 'owner_assumed':
        diagnostics.append('source_timezone_assumed:Europe/Amsterdam')
    if not cutoff_eligible:
        diagnostics.append('source_timezone_unverified:cutoff_eligibility_unavailable')
    cost_evidence = settings.get('cost_history', {})
    cost_complete = cost_evidence.get('verified') is True and bool(cost_evidence.get('evidence'))
    if not cost_complete:
        diagnostics.append('cost_history_completeness_unverified')
    baseline = settings.get('opening_baseline', {})
    verified = baseline.get('verified') is True and bool(baseline.get('evidence'))
    opening = number(baseline.get('cash_eur', 0)) if verified else ZERO
    equity_start = number(baseline.get('equity_eur', 0)) if verified else None
    if verified:
        at = pd.Timestamp(baseline['at'])
        if at.tzinfo is None or at > cutoff or equity_start != opening:
            raise ValueError('Opening baseline requires dated verified cash-only equity; opening holdings require reconciled lots')
        if not frame.empty:
            earliest = pd.to_datetime(frame['normalized_date'] + ' ' + frame['time'], format='mixed').min()
            zone = timing
            if zone:
                earliest = earliest.tz_localize(zone['name'], ambiguous='raise', nonexistent='raise')
                if earliest < at:
                    raise ValueError('Opening baseline must precede all Transactions')
            else:
                verified = False
    if not verified:
        diagnostics.append('verified_opening_baseline_required')
    ordered = sort_transactions_chronologically(frame).to_dict('records')
    cash, external, income, withholding, costs = opening, ZERO, ZERO, ZERO, ZERO
    cash_known = verified
    states, charges, disposals = {}, [], []
    fees = {}
    inline_fx = {}
    for row in ordered:
        if row.get('action') in ('BUY', 'SELL') and row.get('source_format') == 'transactions':
            src = row.get('source_record') or {}
            raw = src.get('autofx kosten') or src.get('autofx fee')
            if raw:
                inline_fx[row['row_hash']] = abs(source_number(raw))
    # Match the two representations only with a shared Asset/date/order and an
    # equal aggregate AutoFX amount. The order groups fills; it is not a fill ID.
    def fx_key(row):
        return (row.get('broker_asset_id'), row['normalized_date'], row.get('order_id') or '')
    def posted_autofx(row):
        return row['type'] == 'FEE' and bool(re.search(r'\bauto[\s-]*fx\b', row['description'], re.I))
    inline_groups, posted_groups = {}, {}
    for row in ordered:
        if row['row_hash'] in inline_fx:
            inline_groups.setdefault(fx_key(row), []).append(row)
        if posted_autofx(row):
            posted_groups.setdefault(fx_key(row), []).append(row)
    matched_inline, matched_postings = set(), set()
    for key, executions in inline_groups.items():
        possible = [other for other in posted_groups if other[:2] == key[:2] and (not other[2] or not key[2])]
        if possible:
            raise ValueError('ambiguous_autofx_fee_overlap_requires_review')
        postings = posted_groups.get(key, [])
        if not postings:
            continue
        inline_total = sum((inline_fx[row['row_hash']] for row in executions), ZERO)
        if any(eur_rate(row, settings) is None for row in postings):
            raise ValueError('ambiguous_autofx_fee_overlap_requires_review')
        posted_total = sum((abs(exact(row, 'amount')) * eur_rate(row, settings) for row in postings), ZERO)
        if inline_total != posted_total:
            raise ValueError('ambiguous_autofx_fee_overlap_requires_review')
        matched_inline.update(row['row_hash'] for row in executions)
        matched_postings.update(row['row_hash'] for row in postings)
    for row in ordered:
        if row['type'] == 'FEE' and row.get('order_id') and row['row_hash'] not in matched_postings:
            key = (row.get('broker_asset_id'), row['order_id'])
            fees[key] = fees.get(key, ZERO) + abs(exact(row, 'amount')) * (eur_rate(row, settings) or Decimal(1))
    # Allocate an order's separately posted fees across its executions by quantity.
    quantities = {}
    for row in ordered:
        if row.get('action') in ('BUY', 'SELL'):
            key = (row.get('broker_asset_id'), row.get('order_id'))
            quantities[key] = quantities.get(key, ZERO) + exact(row, 'quantity')
    for row in ordered:
        if row.get('is_cash_sweep') or row['type'] == 'RESERVATION':
            continue
        rate = eur_rate(row, settings)
        amount = exact(row, 'amount') * (rate or Decimal(1))
        if rate is None:
            cash_known = False
            diagnostics.append('missing_verified_eur_cash:' + row['row_hash'])
        cash += amount
        fx_cost = inline_fx.get(row['row_hash'], ZERO)
        if fx_cost and row['row_hash'] not in matched_inline:
            cash -= fx_cost
            charges.append(Charge(row['row_hash'], row['normalized_date'], 'recorded_fx', fx_cost, 'trade'))
        typ = row['type']
        if typ in ('DEPOSIT', 'WITHDRAWAL'):
            external += amount
        elif typ in ('DIVIDEND', 'INTEREST', 'PROMOTION'):
            if amount < 0:
                withholding += abs(amount)
            else:
                income += amount
        elif typ == 'FEE':
            key = (row.get('broker_asset_id'), row.get('order_id'))
            allocation = 'trade' if key in quantities and key[1] else 'portfolio'
            if allocation == 'portfolio':
                costs += abs(amount)
            charges.append(Charge(row['row_hash'], row['normalized_date'], 'recorded_fx' if posted_autofx(row) else 'recorded_fee', abs(amount), allocation))
        if row.get('action') not in ('BUY', 'SELL'):
            continue
        identity = row.get('broker_asset_id') or row.get('isin') or row['raw_product']
        evidence = settings.get('asset_evidence', {}).get(identity, {})
        mapped = evidence.get('verified') is True and bool(evidence.get('evidence')) and evidence.get('symbol') and evidence.get('kind') in ('ETF', 'Stock', 'Cryptocurrency', 'ETP')
        state = states.setdefault(identity, {'lots': [], 'realized': ZERO, 'symbol': evidence.get('symbol') if mapped else None, 'kind': evidence.get('kind') if mapped else 'unverified'})
        if not mapped:
            diagnostics.append('asset_identity_requires_verified_mapping:' + identity)
        qty = exact(row, 'quantity')
        key = (row.get('broker_asset_id'), row.get('order_id'))
        fee = fees.get(key, ZERO) * qty / quantities[key] if key[1] else ZERO
        fee += fx_cost
        cost_known = rate is not None and amount != ZERO
        if not cost_known:
            cash_known = False
            diagnostics.append('missing_trade_cash_or_cost:' + row['row_hash'])
        if typ == 'BUY':
            state['lots'].append(Lot(row['row_hash'], row['normalized_date'], qty, abs(amount) + fee if cost_known else None))
        else:
            remaining, disposed = qty, ZERO
            consumed_lots = []
            cost_points = [{'quantity': ZERO, 'cost_eur': ZERO}]
            while remaining and state['lots']:
                lot = state['lots'].pop(0)
                taken = min(remaining, lot.quantity)
                consumed = lot.cost_eur * taken / lot.quantity if lot.cost_eur is not None else None
                disposed = disposed + consumed if disposed is not None and consumed is not None else None
                if taken < lot.quantity:
                    state['lots'].insert(0, Lot(lot.transaction_id, lot.acquired_at, lot.quantity-taken, lot.cost_eur-consumed if consumed is not None else None))
                remaining -= taken
                consumed_lots.append({'acquisition_id': lot.transaction_id, 'quantity': taken, 'cost_eur': consumed})
                if disposed is not None:
                    cost_points.append({'quantity': qty-remaining, 'cost_eur': disposed})
            if remaining:
                raise ValueError('sale_quantity_exceeds_known_inventory:' + identity)
            gain = amount-fee-disposed if cost_known and disposed is not None and remaining == 0 else None
            state['realized'] = state['realized'] + gain if state['realized'] is not None and gain is not None else None
            executed_at = None
            if cutoff_eligible and row.get('time'):
                executed_at = pd.Timestamp(row['normalized_date']+' '+row['time']).tz_localize(timing['name'], ambiguous='raise', nonexistent='raise').isoformat()
            verified_disposal = cost_complete and cost_known and disposed is not None and cutoff_eligible and executed_at is not None and mapped
            disposals.append({'schema_version': 'canonical-disposal-v1', 'execution_id': row['row_hash'],
                'identity_version': row.get('identity_version'), 'identity_fingerprint': row.get('identity_fingerprint'),
                'identity_occurrence': str(row.get('identity_occurrence', '')), 'broker_asset_id': identity,
                'symbol': state['symbol'], 'asset_kind': state['kind'], 'order_id': row.get('order_id'),
                'executed_at': executed_at, 'source_timezone': timing,
                'quantity': qty, 'gross_proceeds_eur': amount if rate is not None else None,
                'recorded_fees_eur': fee if rate is not None else None, 'fees_eur': fee if verified_disposal else None,
                'disposed_cost_eur': disposed if verified_disposal else None, 'realized_gain_eur': gain if verified_disposal else None,
                'coverage': 'verified_complete' if verified_disposal else 'unverified',
                'allocation_policy': 'canonical40-breakpoints-exact-rational-v1',
                'cost_breakpoints': cost_points if verified_disposal else [], 'consumed_lots': consumed_lots})
            if gain is None:
                diagnostics.append('missing_disposed_cost:' + identity)
    positions = []
    for identity, state in states.items():
        qty = sum((lot.quantity for lot in state['lots']), ZERO)
        cost = sum((lot.cost_eur for lot in state['lots']), ZERO) if all(l.cost_eur is not None for l in state['lots']) else None
        quote = prices.get(state['symbol'])
        value = qty*number(quote.price_eur) if quote else ZERO if qty == 0 else None
        if value is None:
            diagnostics.append('missing_observed_value:' + identity)
        positions.append(Position(identity, state['symbol'], state['kind'], qty, tuple(state['lots']), cost, 'verified_complete' if cost_complete else 'recorded_only_incomplete', value, value-cost if value is not None and cost is not None and cost_complete and cutoff_eligible else None, state['realized'] if cost_complete and cutoff_eligible else None))
    market = sum((p.market_value_eur for p in positions), ZERO) if all(p.market_value_eur is not None for p in positions) else None
    equity = cash+market if cash_known and market is not None else None
    gain = equity-equity_start-external if verified and cutoff_eligible and equity is not None and cost_complete else None
    attributed = sum((p.held_gain_eur+p.realized_gain_eur for p in positions), ZERO)+income-withholding-costs if verified and cutoff_eligible and cost_complete and all(p.held_gain_eur is not None and p.realized_gain_eur is not None for p in positions) else None
    if attributed is None:
        gain = None
    if gain is not None and attributed is not None and abs(gain-attributed) > Decimal('0.00000001'):
        diagnostics.append('equity_bridge_does_not_reconcile')
        gain = attributed = None
    return Ledger('ledger-v1', tuple(positions), tuple(charges), cash if cash_known else None, external, market, equity, gain, attributed, income, withholding, income-withholding, costs, tuple(sorted(set(diagnostics))), tuple(disposals))



