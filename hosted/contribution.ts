import Decimal from 'decimal.js';
import type { Targets } from './targets';
import { timestamp } from './read-model';
const D = Decimal.clone({ precision: 80, rounding: Decimal.ROUND_HALF_EVEN });
export interface ExecutionTerms {
  asset_id: string; revision: string; quantity_step: string; minimum_quantity: string; minimum_notional_eur: string;
  fixed_fee_eur: string; fee_rate_pct: string; minimum_fee_eur: string; fee_status: 'known' | 'estimated'; evidence: string;
  valid_from: string; valid_until: string;
}
type Model = Record<string, any>;
export interface ContributionPlan {
  state: 'complete' | 'incomplete'; budget_eur: string; invested_eur: string | null; fees_eur: string | null; remaining_cash_eur: string;
  diagnostics: string[]; policy: string; purchases: Record<string, string>[]; allocation: Record<string, string | null>[];
}
const numeric = (value: unknown): value is string => typeof value === 'string' && /^\d{1,12}(?:\.\d{1,18})?$/.test(value);
function validTerms(terms: ExecutionTerms, now: string) {
  return terms && typeof terms.revision === 'string' && terms.revision.length > 0 && typeof terms.evidence === 'string' && terms.evidence.length > 0
    && ['known','estimated'].includes(terms.fee_status) && timestamp(terms.valid_from) && timestamp(terms.valid_until)
    && Date.parse(terms.valid_from) <= Date.parse(now) && Date.parse(terms.valid_until) >= Date.parse(now)
    && ['quantity_step','minimum_quantity','minimum_notional_eur','fixed_fee_eur','fee_rate_pct','minimum_fee_eur'].every(key => numeric(terms[key as keyof ExecutionTerms]))
    && new D(terms.quantity_step).gt(0) && new D(terms.minimum_quantity).gte(terms.quantity_step) && new D(terms.fee_rate_pct).lte(100);
}
export function planContribution(model: Model, settings: Targets, terms: ExecutionTerms[], budgetInput: unknown, now: string): ContributionPlan {
  if (typeof budgetInput !== 'string' || !/^\d{1,12}(?:\.\d{1,2})?$/.test(budgetInput)) throw Error('invalid_budget');
  const budget = new D(budgetInput);
  const result: ContributionPlan = { state: 'incomplete', budget_eur: budget.toFixed(), invested_eur: null, fees_eur: null, remaining_cash_eur: budget.toFixed(),
    diagnostics: [], policy: 'Allocate budget proportionally to positive ETF shortfalls against holdings plus this contribution. Sort descending shortfall, then ascending Asset identifier. Round quantities down to verified steps; keep all rounding remainder as cash. Fees included in each allocation envelope. Manual purchase estimates only.', purchases: [], allocation: [] };
  const diagnostics = result.diagnostics;
  const positions: Model[] = model.ledger?.positions ?? [];
  if (settings.version !== model.settings_version) diagnostics.push('settings_changed_refresh_required');
  if (!settings.targets.length || new Set(settings.targets.map(row => row.asset_id)).size !== settings.targets.length
    || settings.targets.some(row => !numeric(row.target_pct) || new D(row.target_pct).gt(100))
    || !settings.targets.reduce((sum, row) => sum.plus(numeric(row.target_pct) ? row.target_pct : '0'), new D(0)).eq(100)) diagnostics.push('invalid_targets');
  if (model.ledger?.market_value_eur === null || !positions.length || positions.some(row => row.market_value_eur === null)) diagnostics.push('incomplete_current_valuation');
  if (diagnostics.length) return result;
  const market = new D(model.ledger.market_value_eur);
  if (!positions.reduce((sum, row) => sum.plus(row.market_value_eur), new D(0)).eq(market)) { diagnostics.push('inconsistent_current_valuation'); return result; }
  const candidates: { position: Model; shortfall: Decimal; terms: ExecutionTerms; price: Decimal; observed: string }[] = [];
  for (const target of settings.targets) {
    const position = positions.find(row => row.broker_asset_id === target.asset_id);
    if (!position) { diagnostics.push('unknown_target_asset:' + target.asset_id); continue; }
    if (position.asset_kind !== 'ETF') continue;
    const shortfall = D.max(0, market.plus(budget).mul(target.target_pct).div(100).minus(position.market_value_eur));
    if (shortfall.isZero() || budget.isZero()) continue;
    const quote = model.observed_prices?.[position.symbol];
    const rule = terms.find(row => row.asset_id === target.asset_id);
    if (!quote || !numeric(quote.price_eur) || !new D(quote.price_eur).gt(0) || !timestamp(quote.observed_at) || Date.parse(quote.observed_at) > Date.parse(now)) {
      diagnostics.push('missing_eligible_price:' + target.asset_id); continue;
    }
    if (!rule || !validTerms(rule, now)) { diagnostics.push('missing_reviewed_execution_terms:' + target.asset_id); continue; }
    candidates.push({ position, shortfall, terms: rule, price: new D(quote.price_eur), observed: quote.observed_at });
  }
  if (diagnostics.length) return result;
  candidates.sort((a,b) => b.shortfall.comparedTo(a.shortfall) || (a.position.broker_asset_id < b.position.broker_asset_id ? -1 : a.position.broker_asset_id > b.position.broker_asset_id ? 1 : 0));
  const totalShortfall = candidates.reduce((sum, row) => sum.plus(row.shortfall), new D(0));
  let invested = new D(0), fees = new D(0);
  for (const candidate of candidates) {
    const { position, shortfall, terms: rule, price, observed } = candidate;
    const envelope = D.min(shortfall, budget.mul(shortfall).div(totalShortfall));
    const step = new D(rule.quantity_step);
    const fee = (notional: Decimal) => D.max(rule.minimum_fee_eur, new D(rule.fixed_fee_eur).plus(notional.mul(rule.fee_rate_pct).div(100))).toDecimalPlaces(2, Decimal.ROUND_CEIL);
    let low = new D(0), high = envelope.div(price).div(step).floor();
    // Integer bisection avoids loops proportional to budget or fractional precision.
    while (low.lt(high)) {
      const middle = low.plus(high).plus(1).div(2).floor();
      const notional = middle.mul(step).mul(price);
      if (notional.plus(fee(notional)).lte(envelope)) low = middle; else high = middle.minus(1);
    }
    const quantity = low.mul(step), notional = quantity.mul(price);
    if (quantity.isZero() || quantity.lt(rule.minimum_quantity) || notional.lt(rule.minimum_notional_eur)) continue;
    const charge = fee(notional);
    invested = invested.plus(notional); fees = fees.plus(charge);
    result.purchases.push({ asset_id: position.broker_asset_id, symbol: position.symbol, quantity: quantity.toFixed(), price_eur: price.toFixed(),
      notional_eur: notional.toFixed(), fee_eur: charge.toFixed(), total_cost_eur: notional.plus(charge).toFixed(), fee_status: rule.fee_status,
      terms_revision: rule.revision, terms_evidence: rule.evidence, terms_valid_until: rule.valid_until, quote_observed_at: observed, quantity_step: rule.quantity_step });
  }
  if (invested.plus(fees).gt(budget)) throw Error('budget_invariant');
  const afterMarket = market.plus(invested);
  result.state = 'complete'; result.invested_eur = invested.toFixed(); result.fees_eur = fees.toFixed(); result.remaining_cash_eur = budget.minus(invested).minus(fees).toFixed();
  result.allocation = positions.map(position => {
    const purchase = result.purchases.find(row => row.asset_id === position.broker_asset_id);
    const after = new D(position.market_value_eur).plus(purchase?.notional_eur ?? '0');
    return { asset_id: position.broker_asset_id, symbol: position.symbol, before_value_eur: position.market_value_eur, after_value_eur: after.toFixed(),
      before_pct: market.isZero() ? null : new D(position.market_value_eur).div(market).mul(100).toDecimalPlaces(12).toFixed(),
      after_pct: afterMarket.isZero() ? null : after.div(afterMarket).mul(100).toDecimalPlaces(12).toFixed(),
      target_pct: settings.targets.find(row => row.asset_id === position.broker_asset_id)?.target_pct ?? null };
  });
  return result;
}
