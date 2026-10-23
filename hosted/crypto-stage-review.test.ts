import { expect, test } from 'vitest';
import { reviewReachedStages } from './crypto-stage-review';
export const now = '2026-10-23T12:00:00Z';
export function context(cost = '480') {
  return { snapshot: { generation_id: 'g1', read_model: { ledger_version: 'ledger1', settings_version: 'financial1', ledger_cutoff: now, calculation_version: 'decimal-accounting-v1',
    ledger: { positions: [{ broker_asset_id: 'btc', symbol: 'BTC-EUR', asset_kind: 'Cryptocurrency', quantity: '1', retained_cost_eur: cost, cost_coverage: 'verified_complete' }] },
    observed_prices: { 'BTC-EUR': { price_eur: '500', observed_at: '2026-10-23T11:59:00Z', provider: 'synthetic quote', currency: 'EUR', adjustment_basis: 'unadjusted' } },
    disposal_cost_projections: { btc: { schema_version: 'bounded-disposal-curve-v1', broker_asset_id: 'btc', ledger_version: 'ledger1', financial_settings_version: 'financial1', ledger_cutoff: now, cutoff_eligible: true, calculation_version: 'decimal-accounting-v1', state: 'available', cost_coverage: 'verified_complete', quantity_limit: '1', maximum_hypothetical_disposals: '3', precision_policy: 'canonical40-consumer80-outward-bound-v1', absolute_error_bound_eur: '1E-30', breakpoints: [{ quantity: '0', cost_eur: '0' }, { quantity: '1', cost_eur: cost }] } },
  } }, state: { version: '1', plan: { plan_id: 'p1', coin: 'BTC-EUR', asset_id: 'btc', symbol: 'BTC-EUR', state: 'accepted', held_quantity_at_acceptance: '1', core_quantity: '0.1', terms_revision: 'quantity1', quantity_terms_revision: 'quantum1', stages: [{ stage_id: 's1', quantity: '0.5', level_eur: '400', state: 'unfinished' }] } },
  fees: { asset_id: 'btc', revision: 'fee1', permission_revision: 'quantity1', quantity_terms_revision: 'quantum1', fixed_fee_eur: '2.5', fee_rate_pct: '0', minimum_fee_eur: '0', spread_allowance_pct: '0', fee_status: 'known', all_costs_reviewed: true, evidence: 'synthetic all sale charges', spread_evidence: 'synthetic zero spread allowance', valid_from: '2026-01-01T00:00:00Z', valid_until: '2027-01-01T00:00:00Z', permission_valid_from: '2026-01-01T00:00:00Z', permission_valid_until: '2027-01-01T00:00:00Z', quantity_valid_from: '2026-01-01T00:00:00Z', quantity_valid_until: '2027-01-01T00:00:00Z' } };
}
test('net estimated proceeds and canonical actual-unit cost determine gain, never target fills', () => {
  const value = context();
  const result = reviewReachedStages(value.snapshot, value.state, value.fees, now);
  expect(result.stages[0].gross_proceeds_eur).toBe('250');
  expect(result.stages[0].estimated_gain_eur).toBe('7.50');
  expect(result.stages[0].profit_status).toBe('estimated_profit_verified_inputs');
  const loss = reviewReachedStages(context('520').snapshot, value.state, value.fees, now);
  expect(loss.stages[0].estimated_gain_eur).toBe('-12.50');
  expect(loss.stages[0].profit_status).toBe('estimated_loss');
});

test('118k reviews every unfinished 100k and115k stage without marking execution', () => {
  const value = context();
  value.snapshot.read_model.observed_prices['BTC-EUR'].price_eur = '118000';
  value.state.plan.stages = ['100000','115000','125000'].map((level, index) => ({ stage_id: 's'+index,quantity:'0.2',level_eur:level,state:'unfinished' }));
  const result = reviewReachedStages(value.snapshot,value.state,value.fees,now);
  expect(result.stages.map((row: any) => row.level_eur)).toEqual(['100000','115000']);
  expect(result.stages[0].gross_proceeds_eur).toBe('23600');
  expect(value.state.plan.stages.every(stage => stage.state === 'unfinished')).toBe(true);
});

test('stale quotes suppress current prompts; missing fees, pending order and boundary gains remain unverified', () => {
  const value = context();
  expect(reviewReachedStages(value.snapshot,value.state,null,now).stages[0].profit_status).toBe('profit_unverified');
  const pending = reviewReachedStages(value.snapshot,value.state,value.fees,now,
    { matched_quantity:'0',pending_quantity:'0.1',stages:{s1:{matched_quantity:'0',pending_quantity:'0.1'}} });
  expect(pending.stages[0].quantity).toBe('0.4');
  expect(pending.stages[0].profit_status).toBe('profit_unverified');
  value.snapshot.read_model.observed_prices['BTC-EUR'].observed_at = '2026-10-23T11:54:00Z';
  expect(reviewReachedStages(value.snapshot,value.state,value.fees,now).stages).toEqual([]);
  value.snapshot.read_model.observed_prices['BTC-EUR'].observed_at = '2026-10-23T11:59:00Z';
  const boundary = context('495');
  expect(reviewReachedStages(boundary.snapshot,boundary.state,boundary.fees,now).stages[0].profit_status).toBe('profit_unverified_rounding_boundary');
});

test('mandatory net gain examples retain core and treat imported completed quantity only once', () => {
  for (const [cost, gain] of [['960','15.00'],['1040','-25.00']]) {
    const value = context(cost);
    const position = value.snapshot.read_model.ledger.positions[0]; position.quantity = '2';
    const curve = value.snapshot.read_model.disposal_cost_projections.btc;
    curve.quantity_limit = '2'; curve.breakpoints[1].quantity = '2';
    value.state.plan.held_quantity_at_acceptance = '2'; value.state.plan.core_quantity = '0.5'; value.state.plan.stages[0].quantity = '1';
    value.fees.fixed_fee_eur = '5';
    expect(reviewReachedStages(value.snapshot,value.state,value.fees,now).stages[0].estimated_gain_eur).toBe(gain);
  }
  const value = context('384');
  value.snapshot.read_model.ledger.positions[0].quantity = '0.8';
  value.snapshot.read_model.disposal_cost_projections.btc.quantity_limit = '0.8';
  value.snapshot.read_model.disposal_cost_projections.btc.breakpoints[1].quantity = '0.8';
  const review = reviewReachedStages(value.snapshot,value.state,value.fees,now,
    {matched_quantity:'0.2',pending_quantity:'0',stages:{s1:{matched_quantity:'0.2',pending_quantity:'0'}}});
  expect(review.stages[0].quantity).toBe('0.3');
  expect(review.available_tactical_quantity).toBe('0.7');
});
