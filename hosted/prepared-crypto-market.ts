import { completedLevels, suggestedLevels, type Templates } from './crypto-levels';
import { timestamp } from './read-model';
const day = 86400000;
const record = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
// Exact ordering of bounded positive decimal strings; never a Number price.
function normalized(value: unknown): [string, string] | null {
  if (typeof value !== 'string' || value.length > 256 || !/^\d+(?:\.\d+)?$/.test(value) || !/[1-9]/.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return [whole.replace(/^0+/, '') || '0', fraction.replace(/0+$/, '')];
}
function compare(a: [string,string], b: [string,string]) {
  if (a[0].length !== b[0].length) return a[0].length - b[0].length;
  if (a[0] !== b[0]) return a[0] < b[0] ? -1 : 1;
  const length = Math.max(a[1].length,b[1].length), x=a[1].padEnd(length,'0'), y=b[1].padEnd(length,'0');
  return x < y ? -1 : x > y ? 1 : 0;
}
export function preparedLevels(coin: string, version: string | undefined, input: unknown, now: string, templates: Templates) {
  const current = Date.parse(now), midnight = Math.floor(current/day)*day;
  const paused = () => ({ ...suggestedLevels(coin, null, now, templates), diagnostics: ['prepared_history_unavailable'] });
  if (!record(input) || input.schema !== 'prepared-crypto-market-v1' || input.coin !== coin || !version || input.version !== version
    || input.cutoff !== new Date(midnight).toISOString().replace('.000Z','Z')
    || !timestamp(input.prepared_at) || Date.parse(input.prepared_at) < midnight || Date.parse(input.prepared_at) > current
    || input.required_days !== '365' || input.available_days !== '365' || input.currency !== 'EUR' || input.adjustment_basis !== 'unadjusted'
    || typeof input.provider !== 'string' || !input.provider || input.provider.length > 200
    || !Array.isArray(input.sorted_prices) || input.sorted_prices.length !== 365
    || !Array.isArray(input.context_prices) || input.context_prices.length !== 90
    || !Array.isArray(input.context_retrieved_at) || input.context_retrieved_at.length !== 90) return paused();
  let previous: [string,string] | null = null;
  const available = new Map<string,number>();
  for (const price of input.sorted_prices) {
    const exact = normalized(price);
    if (!exact || (previous && compare(previous,exact)>0)) return paused();
    previous=exact; available.set(price,(available.get(price)||0)+1);
  }
  const retrieved = new Map<string,number>();
  const context = [];
  for (let n=0;n<90;n++) {
    const price=input.context_prices[n], at=input.context_retrieved_at[n], observed=midnight-(89-n)*day;
    if (!normalized(price) || !(available.get(price)||0) || typeof at !== 'string') return paused();
    available.set(price,available.get(price)!-1);
    if (!retrieved.has(at)) retrieved.set(at,timestamp(at)?Date.parse(at):NaN);
    const time=retrieved.get(at)!;
    if (!Number.isFinite(time) || time<observed || time>Date.parse(input.prepared_at)) return paused();
    context.push({day:new Date(observed-day).toISOString().slice(0,10),price_eur:price,
      observed_at:new Date(observed).toISOString(),retrieved_at:at,provider:input.provider});
  }
  return {coin,templates,generated_at:now,valid_until:new Date(midnight+day).toISOString(),
    window_start:new Date(midnight-365*day).toISOString().slice(0,10),window_end:new Date(midnight-day).toISOString().slice(0,10),
    available_days:'365',required_days:'365',missing_days:[],context,...completedLevels(input.sorted_prices,templates),
    explanation:'Historical EUR distribution positions, not predicted prices or probabilities of profit. Personal gain, drawdown and allocation are separate. Purchases require an explicitly allocated contribution; no Transaction is executed.'};
}
