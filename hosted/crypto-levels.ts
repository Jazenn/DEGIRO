import Decimal from 'decimal.js';
import { timestamp } from './read-model';
const D = Decimal.clone({ precision: 40 });
export const defaultPercentiles = { purchase: ['35', '20', '10'], sale: ['75', '90', '95'] };
export interface Templates { purchase: string[]; sale: string[] }
const record = (value: unknown): value is Record<string, any> => !!value && typeof value === 'object' && !Array.isArray(value);
function percentile(value: unknown) {
  if (typeof value !== 'string' || !/^\d{1,3}(?:\.\d{1,4})?$/.test(value) || new D(value).gt(100)) throw Error('invalid_percentiles');
  return new D(value);
}
export function validateTemplates(value: unknown): Templates {
  if (!record(value) || !Array.isArray(value.purchase) || !Array.isArray(value.sale)
      || value.purchase.length !== 3 || value.sale.length !== 3) throw Error('invalid_percentiles');
  [...value.purchase, ...value.sale].forEach(percentile);
  return { purchase: [...value.purchase], sale: [...value.sale] };
}
function fromSorted(sorted: Decimal[], p: string) {
  const position = new D(sorted.length - 1).mul(percentile(p)).div(100);
  const index = position.floor().toNumber();
  return sorted[index].plus((sorted[index + 1] || sorted[index]).minus(sorted[index]).mul(position.minus(index))).toFixed();
}
export function linearPercentile(values: string[], p: string) {
  if (!values.length || values.length > 400) throw Error('invalid_observations');
  const sorted = values.map(value => { const price = new D(value); if (!price.isFinite() || !price.gt(0)) throw Error('invalid_observations'); return price; })
    .sort((a, b) => a.cmp(b));
  return fromSorted(sorted, p);
}
interface Level { percentile: string; price_eur: string }
interface Context { day: string; price_eur: string; observed_at: string; retrieved_at: string; provider: string }
export function suggestedLevels(coin: string, input: unknown, now: string, requested: Templates = defaultPercentiles) {
  if (!['BTC-EUR', 'ETH-EUR'].includes(coin)) throw Error('invalid_coin');
  const templates = validateTemplates(requested);
  const current = Date.parse(now);
  if (!Number.isFinite(current)) throw Error('invalid_clock');
  const midnight = Math.floor(current / 86400000) * 86400000;
  const quotes = new Map<number, Context>();
  const diagnostics: string[] = [];
  if (record(input) && Object.keys(input).length <= 400) for (const [at, row] of Object.entries(input)) {
    const time = Date.parse(at);
    // A following midnight closes yesterday. Today's intraday tail is excluded.
    if (!timestamp(at) || !Number.isFinite(time) || time % 86400000 || time > midnight || time <= midnight - 365 * 86400000) continue;
    if (!record(row) || typeof row.price_eur !== 'string' || !/^\d+(?:\.\d+)?$/.test(row.price_eur)
        || !new D(row.price_eur).gt(0) || row.currency !== 'EUR' || row.adjustment_basis !== 'unadjusted'
        || !timestamp(row.observed_at) || Date.parse(row.observed_at) !== time || !row.provider || typeof row.provider !== 'string'
        || !timestamp(row.retrieved_at) || Date.parse(row.retrieved_at) < time || Date.parse(row.retrieved_at) > current) {
      diagnostics.push('invalid_daily_observation'); continue;
    }
    const quote = { day: new Date(time - 86400000).toISOString().slice(0, 10), price_eur: row.price_eur,
      observed_at: new Date(time).toISOString(), retrieved_at: row.retrieved_at, provider: row.provider };
    const previous = quotes.get(time);
    if (previous && (previous.price_eur !== quote.price_eur || previous.provider !== quote.provider)) diagnostics.push('conflicting_daily_observation');
    quotes.set(time, quote);
  }
  const observations: Context[] = [], missing: string[] = [];
  for (let n = 364; n >= 0; n--) {
    const time = midnight - n * 86400000;
    const row = quotes.get(time);
    if (row) observations.push(row); else missing.push(new Date(time - 86400000).toISOString().slice(0, 10));
  }
  if (new Set(observations.map(row => row.provider)).size > 1) diagnostics.push('inconsistent_daily_source');
  const result = { coin, state: 'paused', templates, generated_at: now,
    valid_until: new Date(midnight + 86400000).toISOString(),
    window_start: new Date(midnight - 365 * 86400000).toISOString().slice(0, 10),
    window_end: new Date(midnight - 86400000).toISOString().slice(0, 10),
    available_days: String(observations.length), required_days: '365', missing_days: missing,
    context: observations.filter(row => Date.parse(row.observed_at) > midnight - 90 * 86400000),
    purchase: [] as Level[], sale: [] as Level[], diagnostics,
    explanation: 'Historical EUR distribution positions, not predicted prices or probabilities of profit. Personal gain, drawdown and allocation are separate. Purchases require an explicitly allocated contribution; no Transaction is executed.' };
  if (missing.length || diagnostics.length) { result.diagnostics.push('complete_daily_window_required'); return result; }
  const sorted = observations.map(row => new D(row.price_eur)).sort((a, b) => a.cmp(b));
  result.purchase = templates.purchase.map(p => ({ percentile: p, price_eur: fromSorted(sorted, p) }));
  result.sale = templates.sale.map(p => ({ percentile: p, price_eur: fromSorted(sorted, p) }));
  const levels = [...result.purchase.slice().reverse(), ...result.sale].map(row => new D(row.price_eur));
  const ordered = levels.every((price, index) => !index || price.gt(levels[index - 1]));
  result.state = ordered ? 'ready' : 'review';
  if (!ordered) result.diagnostics.push('coincident_or_unordered_levels_require_review');
  return result;
}
