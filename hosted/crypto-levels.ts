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
function fromSorted(sorted: readonly (Decimal | string)[], p: string) {
  const position = new D(sorted.length - 1).mul(percentile(p)).div(100);
  const index = position.floor().toNumber();
  const lower = new D(sorted[index]), upper = new D(sorted[index + 1] || sorted[index]);
  return lower.plus(upper.minus(lower).mul(position.minus(index))).toFixed();
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
  // These caches live for one calculation only: edits and new market versions are
  // always revalidated. Provider retrieval timestamps commonly repeat 365 times.
  const times = new Map<string, number>();
  const checkedTime = (value: unknown): number => {
    if (typeof value !== 'string') return NaN;
    if (times.has(value)) return times.get(value)!;
    const time = timestamp(value) ? Date.parse(value) : NaN;
    times.set(value, time);
    return time;
  };
  const quotes = new Map<number, Context>();
  const prices = new Map<number, Decimal>();
  const diagnostics: string[] = [];
  if (record(input) && Object.keys(input).length <= 400) for (const [at, row] of Object.entries(input)) {
    const time = checkedTime(at);
    // A following midnight closes yesterday. Today's intraday tail is excluded.
    if (!Number.isFinite(time) || time % 86400000 || time > midnight || time <= midnight - 365 * 86400000) continue;
    if (!record(row) || typeof row.price_eur !== 'string' || !/^\d+(?:\.\d+)?$/.test(row.price_eur)
        || row.currency !== 'EUR' || row.adjustment_basis !== 'unadjusted'
        || checkedTime(row.observed_at) !== time || !row.provider || typeof row.provider !== 'string'
        || !Number.isFinite(checkedTime(row.retrieved_at)) || checkedTime(row.retrieved_at) < time || checkedTime(row.retrieved_at) > current) {
      diagnostics.push('invalid_daily_observation'); continue;
    }
    const price = new D(row.price_eur);
    if (!price.gt(0)) { diagnostics.push('invalid_daily_observation'); continue; }
    const quote = { day: new Date(time - 86400000).toISOString().slice(0, 10), price_eur: row.price_eur,
      observed_at: new Date(time).toISOString(), retrieved_at: row.retrieved_at, provider: row.provider };
    const previous = quotes.get(time);
    if (previous && (previous.price_eur !== quote.price_eur || previous.provider !== quote.provider)) diagnostics.push('conflicting_daily_observation');
    quotes.set(time, quote);
    prices.set(time, price);
  }
  const observations: Context[] = [], missing: string[] = [], context: Context[] = [];
  const orderedPrices: Decimal[] = [];
  for (let n = 364; n >= 0; n--) {
    const time = midnight - n * 86400000;
    const row = quotes.get(time);
    if (row) {
      observations.push(row);
      orderedPrices.push(prices.get(time)!);
      if (n < 90) context.push(row);
    } else missing.push(new Date(time - 86400000).toISOString().slice(0, 10));
  }
  if (new Set(observations.map(row => row.provider)).size > 1) diagnostics.push('inconsistent_daily_source');
  const result = { coin, state: 'paused', templates, generated_at: now,
    valid_until: new Date(midnight + 86400000).toISOString(),
    window_start: new Date(midnight - 365 * 86400000).toISOString().slice(0, 10),
    window_end: new Date(midnight - 86400000).toISOString().slice(0, 10),
    available_days: String(observations.length), required_days: '365', missing_days: missing,
    context,
    purchase: [] as Level[], sale: [] as Level[], diagnostics,
    explanation: 'Historical EUR distribution positions, not predicted prices or probabilities of profit. Personal gain, drawdown and allocation are separate. Purchases require an explicitly allocated contribution; no Transaction is executed.' };
  if (missing.length || diagnostics.length) { result.diagnostics.push('complete_daily_window_required'); return result; }
  const sorted = orderedPrices.sort((a, b) => a.cmp(b));
  return { ...result, ...completedLevels(sorted, templates) };
}

// Both raw offline/reference and prepared hosted paths share exact interpolation.
export function completedLevels(sorted: readonly (Decimal | string)[], templates: Templates) {
  const purchase = templates.purchase.map(p => ({ percentile: p, price_eur: fromSorted(sorted, p) }));
  const sale = templates.sale.map(p => ({ percentile: p, price_eur: fromSorted(sorted, p) }));
  const levels = [...purchase.slice().reverse(), ...sale].map(row => new D(row.price_eur));
  const ordered = levels.every((price, index) => !index || price.gt(levels[index - 1]));
  return { purchase, sale, state: ordered ? 'ready' : 'review',
    diagnostics: ordered ? [] : ['coincident_or_unordered_levels_require_review'] };
}
