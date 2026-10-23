import Decimal from 'decimal.js';
import { timestamp } from './read-model';
import { validateTemplates, type Templates } from './crypto-levels';
const D = Decimal.clone({ precision: 80, rounding: Decimal.ROUND_DOWN });
export interface PlanTerms {
  coin: string; asset_id: string; symbol: string; revision: string; quantity_terms_revision: string;
  quantity_step: string; minimum_quantity: string; minimum_notional_eur: string;
  evidence: string; quantity_evidence: string; valid_from: string; valid_until: string;
  quantity_valid_from: string; quantity_valid_until: string;
}
export interface PlanRequest {
  coin: string; operation_id: string; expected_version: string; generation_id: string; market_version: string;
  terms_revision: string; core_quantity: string; proportions: string[]; levels_eur: string[];
  templates: Templates;
}
export const validCoin = (coin: unknown): coin is string => coin === 'BTC-EUR' || coin === 'ETH-EUR';
const numeric = (value: unknown): value is string => typeof value === 'string' && /^\d{1,18}(?:\.\d{1,18})?$/.test(value);
export function validatePlanRequest(value: unknown): PlanRequest {
  const input = value as PlanRequest;
  if (!input || !validCoin(input.coin) || typeof input.operation_id !== 'string' || !/^[\w-]{8,100}$/.test(input.operation_id)
      || typeof input.expected_version !== 'string' || !/^\d{1,18}$/.test(input.expected_version)
      || !['generation_id', 'market_version', 'terms_revision'].every(key => typeof input[key as keyof PlanRequest] === 'string' && (input[key as keyof PlanRequest] as string).length > 0)
      || !numeric(input.core_quantity) || !new D(input.core_quantity).gt(0)
      || !Array.isArray(input.proportions) || input.proportions.length !== 3
      || !Array.isArray(input.levels_eur) || input.levels_eur.length !== 3
      || ![...input.proportions, ...input.levels_eur].every(value => numeric(value) && new D(value).gt(0))
      || !input.proportions.reduce((sum, value) => sum.plus(value), new D(0)).eq(100)
      || input.levels_eur.some((value, index) => index > 0 && !new D(value).gt(input.levels_eur[index - 1]))) throw Error('invalid_crypto_plan');
  // Retain only declared request fields so idempotency compares a stable contract.
  return { coin: input.coin, operation_id: input.operation_id, expected_version: input.expected_version,
    generation_id: input.generation_id, market_version: input.market_version, terms_revision: input.terms_revision,
    core_quantity: input.core_quantity, proportions: [...input.proportions], levels_eur: [...input.levels_eur], templates: validateTemplates(input.templates) };
}
export function prepareCryptoPlan(snapshot: any, terms: PlanTerms, request: PlanRequest, now: string, market: Record<string, unknown>) {
  const input = validatePlanRequest(request);
  if (!timestamp(now) || !terms || terms.coin !== input.coin || terms.revision !== input.terms_revision
      || !terms.evidence || !terms.quantity_evidence || !terms.quantity_terms_revision
      || !['quantity_step', 'minimum_quantity', 'minimum_notional_eur'].every(key => numeric(terms[key as keyof PlanTerms]))
      || !new D(terms.quantity_step).gt(0) || new D(terms.minimum_quantity).lt(terms.quantity_step)
      || ![['valid_from','valid_until'], ['quantity_valid_from','quantity_valid_until']].every(([from, until]) => timestamp(terms[from as keyof PlanTerms]) && timestamp(terms[until as keyof PlanTerms])
        && Date.parse(terms[from as keyof PlanTerms]) <= Date.parse(now) && Date.parse(now) < Date.parse(terms[until as keyof PlanTerms]))) throw Error('reviewed_sale_quantity_terms_required');
  if (snapshot.generation_id !== input.generation_id) throw Error('snapshot_changed');
  const model = snapshot.read_model;
  const position = model.ledger.positions.find((row: any) => row.broker_asset_id === terms.asset_id);
  if (!position || position.asset_kind !== 'Cryptocurrency' || position.symbol !== terms.symbol
      || typeof position.quantity !== 'string' || !/^\d+(?:\.\d+)?(?:E[+-]?\d+)?$/i.test(position.quantity)
      || !new D(position.quantity).isFinite() || !new D(position.quantity).gt(0)
      || position.cost_coverage !== 'verified_complete'
      || (model.diagnostics ?? []).some((diagnostic: string) => diagnostic.includes('cutoff_eligibility_unavailable'))) throw Error('verified_crypto_holding_required');
  const held = new D(position.quantity), core = new D(input.core_quantity), tactical = held.minus(core);
  if (!tactical.gt(0)) throw Error('positive_tactical_quantity_required');
  const planId = `plan-${input.operation_id}`;
  const stages = input.proportions.map((share, index) => {
    const quantity = tactical.mul(share).div(100).div(terms.quantity_step).floor().mul(terms.quantity_step);
    if (quantity.lt(terms.minimum_quantity) || quantity.isZero() || quantity.mul(input.levels_eur[index]).lt(terms.minimum_notional_eur)) throw Error('stage_below_reviewed_minimum');
    return { stage_id: `${planId}:${index + 1}`, proportion_pct: new D(share).toFixed(),
      quantity: quantity.toFixed(), level_eur: new D(input.levels_eur[index]).toFixed(), state: 'unfinished' };
  });
  const total = stages.reduce((sum, stage) => sum.plus(stage.quantity), new D(0));
  if (total.gt(tactical)) throw Error('core_protection_invariant');
  return { plan_id: planId, coin: input.coin, asset_id: terms.asset_id, symbol: terms.symbol, accepted_at: now,
    plan_version: new D(input.expected_version).plus(1).toFixed(),
    accepted_generation_id: snapshot.generation_id, ledger_version: model.ledger_version,
    financial_settings_version: model.settings_version, calculation_version: model.calculation_version,
    rebalancing_targets_version: model.rebalancing_targets_version ?? null,
    held_quantity_at_acceptance: held.toFixed(), core_quantity: core.toFixed(), original_tactical_quantity: tactical.toFixed(),
    quantity_step: terms.quantity_step, minimum_quantity: terms.minimum_quantity, minimum_notional_eur: terms.minimum_notional_eur,
    terms_revision: terms.revision, quantity_terms_revision: terms.quantity_terms_revision,
    terms_evidence: terms.evidence, quantity_evidence: terms.quantity_evidence,
    rounding_residual_quantity: tactical.minus(total).toFixed(), stages,
    source_market: { ...market, market_version: input.market_version },
    state: 'accepted', explanation: 'Acceptance preserves reviewed quantities and levels. No Transaction is executed.' };
}
