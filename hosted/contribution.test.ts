import { expect, test } from 'vitest';
import { planContribution, type ExecutionTerms } from './contribution';
const terms = (asset_id: string): ExecutionTerms => ({ asset_id, revision: 'review-1', quantity_step: '1', minimum_quantity: '1', minimum_notional_eur: '0',
  fixed_fee_eur: '1', fee_rate_pct: '0', minimum_fee_eur: '0', fee_status: 'estimated', evidence: 'Synthetic reviewed all-in EUR purchase tariff',
  valid_from: '2026-01-01T00:00:00Z', valid_until: '2027-01-01T00:00:00Z' });
const model = { settings_version: '1', ledger: { market_value_eur: '200', positions: [
  { broker_asset_id: 'A', symbol: 'A', asset_kind: 'ETF', market_value_eur: '100', quantity: '1' },
  { broker_asset_id: 'B', symbol: 'B', asset_kind: 'ETF', market_value_eur: '100', quantity: '1' },
] }, observed_prices: { A: { price_eur: '100', observed_at: '2026-10-23T10:00:00Z' }, B: { price_eur: '100', observed_at: '2026-10-23T10:00:00Z' } } };
const settings = { version: '1', targets: [{ asset_id: 'A', target_pct: '50' }, { asset_id: 'B', target_pct: '50' }] };

test('ETF budget pays purchase fees and resolves equal shortfalls by Asset identifier with visible cash', () => {
  const plan = planContribution(model, settings, [terms('B'), terms('A')], '202', '2026-10-23T10:00:00Z');
  expect(plan.state).toBe('complete');
  expect(plan.purchases.map(row => [row.asset_id, row.quantity, row.total_cost_eur])).toEqual([['A','1','101'],['B','1','101']]);
  expect(plan.fees_eur).toBe('2');
  expect(plan.remaining_cash_eur).toBe('0');
  expect(plan.allocation[0]).toMatchObject({ before_pct: '50', after_pct: '50' });
  const tiny = planContribution(model, settings, [terms('A'),terms('B')], '100', '2026-10-23T10:00:00Z');
  expect(tiny.purchases).toEqual([]);
  expect(tiny.remaining_cash_eur).toBe('100');
});

test('fee rounding and verified fractional steps keep all-in spend within budget without using existing cash', () => {
  const one = { ...model, ledger: { ...model.ledger, cash_balance_eur: '100000', market_value_eur: '100', positions: [{ ...model.ledger.positions[0], quantity: '10' }] },
    observed_prices: { A: { price_eur: '10', observed_at: '2026-10-23T10:00:00Z' } } };
  const fractional = { ...terms('A'), quantity_step: '0.1', minimum_quantity: '0.2', minimum_notional_eur: '3', fixed_fee_eur: '0.11' };
  const plan = planContribution(one, { version: '1', targets: [{ asset_id: 'A', target_pct: '100' }] }, [fractional], '5', '2026-10-23T10:00:00Z');
  expect(plan.purchases[0]).toMatchObject({ quantity: '0.4', notional_eur: '4', fee_eur: '0.11', total_cost_eur: '4.11', fee_status: 'estimated' });
  expect(plan.remaining_cash_eur).toBe('0.89');
  const priced = { ...one, observed_prices: { A: { price_eur: '33.33333333', observed_at: '2026-10-23T10:00:00Z' } } };
  const roundedFee = planContribution(priced, { version: '1', targets: [{ asset_id: 'A', target_pct: '100' }] }, [{ ...terms('A'), fixed_fee_eur: '0.1', fee_rate_pct: '1' }], '100', '2026-10-23T10:00:00Z');
  expect(roundedFee.purchases[0]).toMatchObject({ quantity: '2', fee_eur: '0.77', total_cost_eur: '67.43666666' });
  expect(roundedFee.remaining_cash_eur).toBe('32.56333334');
});

test('unknown fees, expired precision evidence and stale settings are visibly incomplete, while zero buys cost zero', () => {
  const now = '2026-10-23T10:00:00Z';
  const missing = planContribution(model, settings, [], '500', now);
  expect(missing.state).toBe('incomplete');
  expect(missing.fees_eur).toBeNull();
  expect(missing.purchases).toEqual([]);
  expect(missing.diagnostics).toContain('missing_reviewed_execution_terms:A');
  expect(planContribution(model, { ...settings, version: '2' }, [], '500', now).diagnostics).toContain('settings_changed_refresh_required');
  expect(planContribution(model, settings, [{ ...terms('A'), valid_until: '2026-01-01T00:00:00Z' },terms('B')], '500', now).state).toBe('incomplete');
  expect(planContribution(model, settings, [], '0', now)).toMatchObject({ state: 'complete', invested_eur: '0', fees_eur: '0', remaining_cash_eur: '0', purchases: [] });
  expect(() => planContribution(model, settings, [], '-1', now)).toThrow('invalid_budget');
});

import { createContribution } from './contribution-store';
import { createApplication } from './application';
import { databaseTransport, env, login } from './auth-test-support';

test('authenticated preview requires the displayed coherent generation and settings and cannot mutate holdings', async () => {
  const snapshot = { generation_id: 'g1', published_at: '2026-10-23T10:00:00Z', data_classification: 'synthetic' as const,
    read_model: { ...model, ledger_version: 'l1', calculation_version: 'decimal-accounting-v1', cutoff: '2026-10-23T10:00:00Z' } };
  const contribution = createContribution({ read: async () => ({ snapshot, settings, terms: [terms('A'),terms('B')] }) }, () => Date.parse('2026-10-23T10:00:00Z'));
  const app = createApplication({ authQuery: databaseTransport(), readAccepted: async () => null, contribution: async value => contribution(value) });
  const cookie = (await login()).session!;
  const call = (value: unknown, origin = env.APP_ORIGIN, authenticated = true) => app(new Request(env.APP_ORIGIN+'/api/contribution', { method: 'POST',
    headers: { Cookie: authenticated ? cookie : '', Origin: origin }, body: JSON.stringify(value) }), env);
  const input = { budget_eur: '202', generation_id: 'g1', settings_version: '1' };
  expect((await call(input, env.APP_ORIGIN, false)).status).toBe(401);
  expect((await call(input, 'https://wrong.test')).status).toBe(403);
  const stale = await call({ ...input, generation_id: 'old' });
  expect(stale.status).toBe(409);
  expect((await stale.json()).state).toBe('stale');
  const response = await call(input);
  expect(response.status).toBe(200);
  expect(await response.json()).toMatchObject({ state: 'complete', generation_id: 'g1', settings_version: '1', invested_eur: '200', fees_eur: '2', remaining_cash_eur: '0' });
  expect(snapshot.read_model.ledger.market_value_eur).toBe('200');
});
