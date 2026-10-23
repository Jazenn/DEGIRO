import Decimal from 'decimal.js';
import type { Targets } from './targets';
import { timestamp } from './read-model';
const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_EVEN });
export interface Quote { price_eur: string; observed_at: string | null; retrieved_at: string; provider: string; currency: 'EUR'; adjustment_basis: 'unadjusted' }
type Model = Record<string, any>;
// Revalue the already reconciled ledger by its observed market-value delta.
// Preserve all accounting eligibility gates and immutable FIFO costs/realizations.
export function revalue(original: Model, settings: Targets, quotes: Record<string, Quote>, now: string): Model {
  const model = structuredClone(original), ledger = model.ledger;
  if (model.calculation_version !== 'decimal-accounting-v1' || ledger.market_value_eur === null) throw Error('reconciled_valuation_required');
  const before = new D(ledger.market_value_eur);
  let market = new D(0);
  const positions = [];
  const eligibility: Record<string, string> = {};
  for (const position of ledger.positions) {
    const quantity = new D(position.quantity);
    if (quantity.isNegative()) throw Error('negative_reconciled_quantity');
    let value = new D(0);
    if (!quantity.isZero()) {
      const quote = quotes[position.symbol];
      if (!quote || !timestamp(quote.observed_at) || !timestamp(quote.retrieved_at) || quote.currency !== 'EUR'
        || quote.adjustment_basis !== 'unadjusted' || !new D(quote.price_eur).isFinite() || !new D(quote.price_eur).isPositive()
        || Date.parse(quote.observed_at!) > Date.parse(now)) throw Error('incomplete_quote_batch');
      if (position.market_value_eur === null) throw Error('reconciled_valuation_required');
      value = quantity.mul(quote.price_eur);
      eligibility[position.symbol] = position.asset_kind === 'Cryptocurrency'
        ? Date.parse(now) - Date.parse(quote.observed_at!) <= 300000 ? 'eligible' : 'stale' : 'not_crypto';
      if (position.held_gain_eur !== null) position.held_gain_eur = new D(position.held_gain_eur).plus(value.minus(position.market_value_eur)).toFixed();
    }
    position.market_value_eur = value.toFixed(); market = market.plus(value);
    positions.push(position);
  }
  const delta = market.minus(before);
  ledger.market_value_eur = market.toFixed();
  for (const key of ['equity_eur', 'net_gain_eur', 'attributed_gain_eur']) {
    if (ledger[key] !== null) ledger[key] = new D(ledger[key]).plus(delta).toFixed();
  }
  model.settings_version = settings.version;
  model.cutoff = now;
  model.observed_prices = quotes;
  model.crypto_quote_eligibility = eligibility;
  model.crypto_quote_eligible_until = Object.fromEntries(Object.keys(eligibility).filter(symbol => eligibility[symbol] !== 'not_crypto')
    .map(symbol => [symbol, new Date(Date.parse(quotes[symbol].observed_at!) + 300000).toISOString()]));
  model.contribution_inputs = { settings_version: settings.version, cutoff: now,
    positions: positions.map(position => ({ asset_id: position.broker_asset_id, symbol: position.symbol, quantity: position.quantity,
      market_value_eur: position.market_value_eur, price_eur: quotes[position.symbol]?.price_eur ?? null,
      actual_pct: market.isZero() ? null : new D(position.market_value_eur).div(market).mul(100).toDecimalPlaces(12).toFixed(),
      target_pct: settings.targets.find(row => row.asset_id === position.broker_asset_id)?.target_pct ?? null })) };
  return model;
}



