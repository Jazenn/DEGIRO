// Validate the canonical wire contract, never recompute financial values.
type ObjectValue = Record<string, unknown>;
const object = (value: unknown): value is ObjectValue => !!value && typeof value === 'object' && !Array.isArray(value);
const string = (value: unknown): value is string => typeof value === 'string' && value.length > 0;
const strings = (value: unknown) => Array.isArray(value) && value.every(string);
const decimal = (value: unknown) => typeof value === 'string' && /^-?\d+(?:\.\d+)?(?:E[+-]?\d+)?$/i.test(value);
const nullableDecimal = (value: unknown) => value === null || decimal(value);
export const timestamp = (value: unknown) => typeof value === 'string'
  && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  && Number.isFinite(Date.parse(value));
const date = (value: unknown) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value));
const amounts = (value: ObjectValue, keys: string[]) => keys.every(key => nullableDecimal(value[key]));
const exact = (item: unknown): boolean => typeof item !== 'number' &&
  (!item || typeof item !== 'object' || Object.values(item).every(exact));
export function validReadModel(value: unknown): value is ObjectValue {
  if (!object(value) || !exact(value) || !string(value.ledger_version) || !string(value.settings_version)
      || value.calculation_version !== 'decimal-accounting-v1' || !timestamp(value.cutoff)
      || !strings(value.diagnostics) || !object(value.observed_prices) || !object(value.ledger)) return false;
  const ledger = value.ledger;
  if (ledger.schema_version !== 'ledger-v1' || !strings(ledger.diagnostics)
      || !amounts(ledger, ['cash_balance_eur', 'market_value_eur', 'equity_eur', 'net_gain_eur', 'attributed_gain_eur'])
      || !['net_external_contributions_eur', 'gross_income_eur', 'withholding_eur', 'net_income_eur', 'portfolio_costs_eur'].every(key => decimal(ledger[key]))
      || !Array.isArray(ledger.positions) || !Array.isArray(ledger.charges)) return false;
  if (!ledger.positions.every(position => object(position) && string(position.broker_asset_id)
      && (position.symbol === null || string(position.symbol)) && string(position.asset_kind) && decimal(position.quantity)
      && string(position.cost_coverage) && amounts(position, ['retained_cost_eur', 'market_value_eur', 'held_gain_eur', 'realized_gain_eur'])
      && Array.isArray(position.lots) && position.lots.every(lot => object(lot) && string(lot.transaction_id)
        && date(lot.acquired_at) && decimal(lot.quantity) && nullableDecimal(lot.cost_eur)))) return false;
  if (!ledger.charges.every(charge => object(charge) && string(charge.transaction_id) && date(charge.date)
      && string(charge.category) && decimal(charge.amount_eur) && string(charge.allocation))) return false;
  return Object.values(value.observed_prices).every(quote => object(quote) && decimal(quote.price_eur)
    && timestamp(quote.observed_at) && string(quote.provider) && quote.currency === 'EUR'
    && quote.adjustment_basis === 'unadjusted' && (quote.retrieved_at === null || timestamp(quote.retrieved_at)));
}
