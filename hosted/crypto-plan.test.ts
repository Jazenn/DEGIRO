import { expect, test } from 'vitest';
import { prepareCryptoPlan, type PlanTerms, type PlanRequest } from './crypto-plan';
import { now, snapshot, terms, request } from './crypto-plan-test-support';
test('explicit original tactical shares round down with visible residual and protected core', () => {
  const plan = prepareCryptoPlan(snapshot, terms, request, now, {});
  expect(plan.original_tactical_quantity).toBe('0.81');
  expect(plan.stages.map(stage => stage.quantity)).toEqual(['0.4','0.2','0.1']);
  expect(plan.rounding_residual_quantity).toBe('0.11');
  expect(plan.core_quantity).toBe('0.2');
  expect(plan.financial_settings_version).toBe('financial1');
});

test('missing core, invalid coverage and infeasible rounded stages require explicit correction', () => {
  for (const edit of [{core_quantity: '0'}, {core_quantity: ''}, {proportions:['50','30','19']}, {levels_eur:['100','100','300']}, {core_quantity:'1.00'}]) {
    expect(() => prepareCryptoPlan(snapshot, terms, { ...request, ...edit }, now, {})).toThrow();
  }
  expect(() => prepareCryptoPlan(snapshot, {...terms, evidence:''}, request, now, {})).toThrow('reviewed_sale_quantity_terms_required');
  expect(() => prepareCryptoPlan(snapshot, {...terms, minimum_notional_eur:'40'}, request, now, {})).toThrow('stage_below_reviewed_minimum');
  expect(() => prepareCryptoPlan(snapshot, terms, request, '2027-01-01T00:00:00Z', {})).toThrow('reviewed_sale_quantity_terms_required');
});

test('canonical small scientific-notation holdings retain verified execution precision', () => {
  const small = structuredClone(snapshot); small.read_model.ledger.positions[0].quantity='1E-8';
  const plan=prepareCryptoPlan(small,{...terms,quantity_step:'0.000000001',minimum_quantity:'0.000000001'},
    {...request,core_quantity:'0.000000002',proportions:['50','25','25']},now,{});
  expect(plan.stages.map(stage=>stage.quantity)).toEqual(['0.000000004','0.000000002','0.000000002']);
  expect(plan.rounding_residual_quantity).toBe('0');
});
