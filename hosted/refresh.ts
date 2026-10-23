import Decimal from 'decimal.js';
import type { AcceptedSnapshot } from './application';
import type { Targets } from './targets';
import { revalue, type Quote } from './valuation';
import type { QuoteMapping } from './quote-provider';
export interface RefreshInput { snapshot: AcceptedSnapshot; settings: Targets; mappings: QuoteMapping[]; planning_symbols?: string[] }
export interface RefreshStore {
  read(signal: AbortSignal): Promise<RefreshInput | null>;
  publish(input: RefreshInput, model: Record<string, unknown>, generation: string, deadline: string, signal: AbortSignal): Promise<boolean>;
}
export function createRefresh(store: RefreshStore, quote: (mapping: QuoteMapping, signal: AbortSignal) => Promise<Quote>, clock = () => Date.now()) {
  let running: Promise<Record<string, unknown>> | null = null;
  return (): Promise<Record<string, unknown>> => {
    if (running) return running;
    const operation = async (): Promise<Record<string, unknown>> => {
      const controller = new AbortController(), start = clock();
      let generation: string | null = null;
      let timedOut = false;
      let timer: ReturnType<typeof setTimeout>;
      const timeout = new Promise<Record<string, unknown>>(resolve => {
        timer = setTimeout(() => { timedOut = true; controller.abort(); resolve({ state: 'retained', reason: 'refresh_timeout', generation_id: generation }); }, 10000);
      });
      const work = async (): Promise<Record<string, unknown>> => {
        try {
          const input = await store.read(controller.signal);
          if (!input) return { state: 'retained', reason: 'no_accepted_snapshot', generation_id: null };
          generation = input.snapshot.generation_id;
          const model = input.snapshot.read_model;
          if (typeof model.valuation_refreshed_at === 'string' && model.settings_version === input.settings.version
            && (input.planning_symbols ?? []).every(symbol => !!(model.observed_prices as Record<string, unknown>)?.[symbol])
            && clock() - Date.parse(model.valuation_refreshed_at) >= 0 && clock() - Date.parse(model.valuation_refreshed_at) < 30000)
            return { state: 'cached', generation_id: generation };
          const positions = (model.ledger as { positions: { symbol: string | null; quantity: string }[] }).positions;
          const symbols = [...new Set(positions.filter(row => !new Decimal(row.quantity).isZero()).map(row => row.symbol).concat(input.planning_symbols ?? []))];
          if (symbols.length > 100 || symbols.some(symbol => !symbol)) throw Error('mapping_required');
          const mappings = symbols.map(symbol => {
            const mapping = input.mappings.find(row => row.symbol === symbol);
            if (!mapping || !mapping.evidence) throw Error('mapping_required'); return mapping;
          });
          const quotes: Record<string, Quote> = {};
          let cursor = 0;
          await Promise.all(Array.from({ length: Math.min(4, mappings.length) }, async () => {
            while (cursor < mappings.length && !controller.signal.aborted) {
              const mapping = mappings[cursor++]; quotes[mapping.symbol] = await quote(mapping, controller.signal);
            }
          }));
          if (controller.signal.aborted) throw Error('timeout');
          const now = new Date(clock()).toISOString();
          const next = revalue(model, input.settings, quotes, now);
          next.valuation_refreshed_at = now;
          const id = crypto.randomUUID();
          if (controller.signal.aborted) throw Error('timeout');
          const saved = await store.publish(input, next, id, new Date(start + 10000).toISOString(), controller.signal);
          return saved ? { state: 'refreshed', generation_id: id } : { state: 'retained', reason: 'concurrent_change', generation_id: generation };
        } catch (error) {
          const known = error instanceof Error && ['mapping_required','incomplete_quote_batch','reconciled_valuation_required'].includes(error.message) ? error.message : 'refresh_failed';
          return { state: 'retained', reason: timedOut ? 'refresh_timeout' : known, generation_id: generation };
        }
      };
      try { return await Promise.race([work(), timeout]); }
      finally { clearTimeout(timer!); }
    };
    running = operation().finally(() => { running = null; });
    return running;
  };
}
