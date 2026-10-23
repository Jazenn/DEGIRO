import Decimal from 'decimal.js';
import { timestamp } from './read-model';
const D = Decimal.clone({ precision: 80, rounding: Decimal.ROUND_HALF_EVEN });
const decimal = (value: unknown) => typeof value === 'string' && /^\d+(?:\.\d+)?(?:E[+-]?\d+)?$/i.test(value) && new D(value).isFinite();
const down = (value: Decimal) => value.toDecimalPlaces(2, Decimal.ROUND_FLOOR);
const up = (value: Decimal) => value.toDecimalPlaces(2, Decimal.ROUND_CEIL);
export interface Progress { matched_quantity: string; pending_quantity: string; reconciled_ledger_version?: string; stages: Record<string, { matched_quantity: string; pending_quantity: string }> }
export const noReports: Progress = { matched_quantity: '0', pending_quantity: '0', stages: {} };
function prepareCostProjection(curve: any, model: any, position: any) {
  if (!curve || curve.state !== 'available' || curve.schema_version !== 'bounded-disposal-curve-v1'
      || curve.precision_policy !== 'canonical40-consumer80-outward-bound-v1' || curve.maximum_hypothetical_disposals !== '3'
      || curve.cutoff_eligible !== true || !timestamp(curve.ledger_cutoff) || curve.ledger_cutoff !== model.ledger_cutoff
      || curve.ledger_version !== model.ledger_version || curve.financial_settings_version !== model.settings_version
      || curve.calculation_version !== model.calculation_version || curve.broker_asset_id !== position.broker_asset_id
      || curve.cost_coverage !== 'verified_complete' || position.cost_coverage !== 'verified_complete'
      || ![curve.quantity_limit, curve.absolute_error_bound_eur, position.retained_cost_eur].every(decimal)
      || !new D(curve.quantity_limit).eq(position.quantity) || !Array.isArray(curve.breakpoints)
      || curve.breakpoints.length < 2 || curve.breakpoints.length > 4097) return null;
  const points = curve.breakpoints;
  if (points.some((p: any) => !decimal(p.quantity) || !decimal(p.cost_eur))) return null;
  if (!new D(points[0].quantity).isZero() || !new D(points[0].cost_eur).isZero()
      || !new D(points.at(-1).quantity).eq(curve.quantity_limit) || !new D(points.at(-1).cost_eur).eq(position.retained_cost_eur)) return null;
  for (let i = 1; i < points.length; i++) {
    const quantity = new D(points[i].quantity).minus(points[i-1].quantity), cost = new D(points[i].cost_eur).minus(points[i-1].cost_eur);
    if (!quantity.gt(0) || quantity.gt('1e18') || quantity.decimalPlaces() > 18 || cost.lt(0) || cost.gt('1e18') || cost.decimalPlaces() > 40) return null;
  }
  const bound = new D(curve.absolute_error_bound_eur);
  if (bound.lt(new D(100).mul(points.length).mul('5e-40').mul(D.max(1, position.retained_cost_eur)))) return null;
  const evaluate = (quantity: Decimal) => {
    let low = 1, high = points.length - 1;
    while (low < high) { const middle = Math.floor((low + high) / 2); if (new D(points[middle].quantity).lt(quantity)) low = middle + 1; else high = middle; }
    const left = points[low-1], right = points[low];
    return new D(left.cost_eur).plus(new D(right.cost_eur).minus(left.cost_eur).mul(quantity.minus(left.quantity)).div(new D(right.quantity).minus(left.quantity)));
  };
  return (start: string, end: string) => {
    if (![start,end].every(decimal)) return null;
    const a=new D(start), b=new D(end);
    if (a.lt(0) || !b.gt(a) || b.gt(curve.quantity_limit) || a.decimalPlaces()>18 || b.decimalPlaces()>18) return null;
    const center = evaluate(b).minus(evaluate(a));
    return { center, lower: D.max(0, center.minus(bound)), upper: center.plus(bound), bound };
  };
}
export function projectedCostInterval(curve: any, model: any, position: any, start: string, end: string) {
  return prepareCostProjection(curve, model, position)?.(start, end) ?? null;
}
function reviewedFees(terms: any, plan: any, now: string) {
  return terms && terms.asset_id === plan.asset_id && terms.permission_revision === plan.terms_revision
    && terms.quantity_terms_revision && plan.quantity_terms_revision
    && terms.quantity_terms_revision === plan.quantity_terms_revision
    && terms.all_costs_reviewed === true && ['known','estimated'].includes(terms.fee_status)
    && terms.evidence && terms.spread_evidence && terms.revision
    && timestamp(terms.valid_from) && timestamp(terms.valid_until) && Date.parse(terms.valid_from) <= Date.parse(now) && Date.parse(now) < Date.parse(terms.valid_until)
    && [['permission_valid_from','permission_valid_until'], ['quantity_valid_from','quantity_valid_until']].every(([from, until]) => timestamp(terms[from]) && timestamp(terms[until]) && Date.parse(terms[from]) <= Date.parse(now) && Date.parse(now) < Date.parse(terms[until]))
    && ['fixed_fee_eur','fee_rate_pct','minimum_fee_eur','spread_allowance_pct'].every(key => decimal(terms[key]))
    && new D(terms.fee_rate_pct).lte(100) && new D(terms.spread_allowance_pct).lte(100);
}
export function reviewReachedStages(snapshot: any, state: any, fees: any, now: string, progress: Progress = noReports) {
  const plan = state.plan;
  const result: Record<string, any> = { state: 'unavailable', reason: 'accepted_plan_required', generation_id: snapshot?.generation_id ?? null,
    plan_version: state.version, plan_id: plan?.plan_id ?? null, stages: [], proceeds_destination: 'Review manually executed net proceeds for ETF contribution planning; no sale or contribution is executed.' };
  if (!plan) return result;
  const model = snapshot?.read_model, position = model?.ledger.positions.find((row: any) => row.broker_asset_id === plan.asset_id);
  if (plan.ledger_version && plan.ledger_version !== model?.ledger_version && progress.reconciled_ledger_version !== model?.ledger_version)
    return { ...result, state: 'review', reason: 'changed_ledger_requires_execution_reconciliation' };
  if (!position || position.symbol !== plan.symbol || position.asset_kind !== 'Cryptocurrency' || !decimal(position.quantity)
      || ![progress.pending_quantity, progress.matched_quantity].every(decimal)
      || plan.state !== 'accepted') return { ...result, state: 'review', reason: 'holdings_or_plan_reconciliation_required' };
  if (plan.stages.length > 3 || Object.values(progress.stages).some(row => !decimal(row.pending_quantity) || !decimal(row.matched_quantity))
      || !Object.values(progress.stages).reduce((sum, row) => sum.plus(row.pending_quantity), new D(0)).eq(progress.pending_quantity)
      || !Object.values(progress.stages).reduce((sum, row) => sum.plus(row.matched_quantity), new D(0)).eq(progress.matched_quantity))
    return { ...result, state: 'review', reason: 'stage_quantity_reconciliation_required' };
  const held = new D(position.quantity), pending = new D(progress.pending_quantity), matched = new D(progress.matched_quantity), core = new D(plan.core_quantity);
  if (held.lt(new D(plan.held_quantity_at_acceptance).minus(matched)) || held.minus(pending).lt(core))
    return { ...result, state: 'review', reason: 'manual_quantity_change_requires_reconciliation' };
  const quote = model.observed_prices[plan.symbol];
  if (!timestamp(now) || !quote || !decimal(quote.price_eur) || !new D(quote.price_eur).gt(0) || new D(quote.price_eur).gt('1e18')
      || quote.currency !== 'EUR' || quote.adjustment_basis !== 'unadjusted' || !timestamp(quote.observed_at)
      || !quote.provider || Date.parse(quote.observed_at) > Date.parse(now) || Date.parse(now) - Date.parse(quote.observed_at) >= 300000)
    return { ...result, state: 'stale', reason: 'current_reference_quote_unavailable_or_expired' };
  result.state = 'ready'; result.reason = null; result.quote = quote;
  result.quote_eligible_until = new Date(Date.parse(quote.observed_at) + 300000).toISOString();
  result.pending_quantity = pending.toFixed(); result.available_tactical_quantity = D.max(0, held.minus(core).minus(pending)).toFixed();
  let prefix = new D(0), total = new D(0);
  const feeCoverage = reviewedFees(fees, plan, now);
  const costProjection = pending.isZero() ? prepareCostProjection(model.disposal_cost_projections?.[plan.asset_id],model,position) : null;
  result.review_eligible_until = feeCoverage ? new Date(Math.min(Date.parse(result.quote_eligible_until),
    Date.parse(fees.valid_until), Date.parse(fees.permission_valid_until), Date.parse(fees.quantity_valid_until))).toISOString() : result.quote_eligible_until;
  for (const stage of plan.stages) {
    const activity = progress.stages[stage.stage_id] || { pending_quantity: '0', matched_quantity: '0' };
    if (![activity.pending_quantity, activity.matched_quantity, stage.quantity, stage.level_eur].every(decimal))
      return { ...result, state: 'review', reason: 'stage_quantity_reconciliation_required', stages: [] };
    const remainder = new D(stage.quantity).minus(activity.pending_quantity).minus(activity.matched_quantity);
    if (remainder.lt(0)) return { ...result, state: 'review', reason: 'stage_quantity_reconciliation_required', stages: [] };
    if (stage.state !== 'unfinished' || remainder.isZero() || new D(quote.price_eur).lt(stage.level_eur)) continue;
    total = total.plus(remainder);
    if (total.gt(result.available_tactical_quantity)) return { ...result, state: 'review', reason: 'core_protection_or_pending_quantity_limit', stages: [] };
    const gross = remainder.mul(quote.price_eur);
    const projection = costProjection?.(prefix.toFixed(), prefix.plus(remainder).toFixed()) ?? null;
    const row: Record<string, any> = { stage_id: stage.stage_id, level_eur: stage.level_eur, quantity: remainder.toFixed(),
      gross_proceeds_eur: gross.toFixed(), profit_status: 'profit_unverified', estimated_gain_eur: null,
      diagnostic: !pending.isZero() ? 'pending_execution_order_requires_canonical_reconciliation' : !projection ? 'canonical_cost_projection_unverified' : !feeCoverage ? 'reviewed_all_in_sale_fees_required' : null };
    if (feeCoverage && projection) {
      const fee = D.max(fees.minimum_fee_eur, new D(fees.fixed_fee_eur).plus(gross.mul(fees.fee_rate_pct).div(100)));
      const spread = gross.mul(fees.spread_allowance_pct).div(100), net = gross.minus(fee), netLower = down(net.minus(spread));
      const costUpper = up(projection.upper), gainLower = netLower.minus(costUpper), gainUpper = up(net).minus(down(projection.lower));
      Object.assign(row, { fee_eur: fee.toFixed(), fee_status: fees.fee_status, fee_revision: fees.revision, fee_evidence: fees.evidence,
        spread_allowance_eur: spread.toFixed(), spread_evidence: fees.spread_evidence,
        net_proceeds_lower_eur: netLower.toFixed(2), net_proceeds_upper_eur: up(net).toFixed(2),
        canonical_cost_estimate_eur: projection.center.toFixed(), canonical_cost_lower_eur: projection.lower.toFixed(), canonical_cost_upper_eur: projection.upper.toFixed(),
        estimated_gain_eur: net.minus(spread).minus(projection.center).toDecimalPlaces(2).toFixed(2),
        gain_lower_eur: gainLower.toFixed(2), gain_upper_eur: gainUpper.toFixed(2),
        profit_status: gainLower.gt(0) ? 'estimated_profit_verified_inputs' : gainUpper.lt(0) ? 'estimated_loss' : 'profit_unverified_rounding_boundary' });
    }
    result.stages.push(row); prefix = prefix.plus(remainder);
  }
  return result;
}
