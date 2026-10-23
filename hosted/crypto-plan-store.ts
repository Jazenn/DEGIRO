import { neon } from '@neondatabase/serverless';
import { neonSnapshotStore } from './snapshot-store';
import { neonCryptoMarketReader, previewCryptoLevels } from './crypto-market-store';
import { prepareCryptoPlan, validatePlanRequest, validCoin, type PlanRequest, type PlanTerms } from './crypto-plan';
import type { Templates } from './crypto-levels';
type Query = (sql: string, params: unknown[]) => Promise<Record<string, any>[]>;
export interface PlanStore {
  read(coin: string): Promise<Record<string, any>>;
  prior(request: PlanRequest): Promise<{ same: boolean; result: Record<string, any> } | null>;
  context(coin: string, templates: Templates): Promise<{ snapshot: any; terms: PlanTerms | null; market: Record<string, any> }>;
  commit(request: PlanRequest, plan: Record<string, any>): Promise<Record<string, any>>;
}
export function cryptoPlans(store: PlanStore, clock = () => new Date().toISOString()) {
  return async (method: string, input: unknown): Promise<Record<string, any>> => {
    if (method === 'GET') {
      if (!validCoin(input)) throw Error('invalid_crypto_plan');
      return store.read(input);
    }
    const request = validatePlanRequest(input);
    const previous = method === 'PREVIEW' ? null : await store.prior(request);
    if (previous) return previous.same ? previous.result : { state: 'conflict', reason: 'operation_id_reused' };
    const state = await store.read(request.coin);
    if (state.version !== request.expected_version) return { state: 'conflict', reason: 'plan_changed' };
    if (state.plan) return { state: 'replacement_required', reason: 'accepted_plan_is_immutable' };
    const context = await store.context(request.coin, request.templates);
    if (!context.snapshot || context.snapshot.generation_id !== request.generation_id) return { state: 'conflict', reason: 'snapshot_changed' };
    if (context.market.market_version !== request.market_version) return { state: 'conflict', reason: 'market_history_changed' };
    if (!['ready','review'].includes(context.market.state)) return { state: 'unavailable', reason: 'complete_market_history_required' };
    const plan = prepareCryptoPlan(context.snapshot, context.terms!, request, clock(), {
      window_start: context.market.window_start, window_end: context.market.window_end,
      generated_at: context.market.generated_at, valid_until: context.market.valid_until,
      templates: context.market.templates,
      providers: [...new Set((context.market.context ?? []).map((row: any) => row.provider))],
      provider_diagnostics: context.market.provider_diagnostics ?? [],
      suggested_sale_levels_eur: (context.market.sale ?? []).map((row: any) => row.price_eur),
    });
    return method === 'PREVIEW' ? { state: 'preview', coin: request.coin, plan } : store.commit(request, plan);
  };
}
export class NeonCryptoPlanStore implements PlanStore {
  constructor(private query: Query, private snapshot: () => Promise<any>, private market: (coin: string, templates: Templates) => Promise<Record<string, any>>) {}
  async terms(coin: string): Promise<PlanTerms | null> {
    const rows = await this.query(`SELECT s.coin,s.asset_id,s.symbol,s.revision,s.quantity_terms_revision,s.evidence,
      q.quantity_step::text,q.minimum_quantity::text,q.minimum_notional_eur::text,q.evidence AS quantity_evidence,
      to_char(s.valid_from AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS valid_from,
      to_char(s.valid_until AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS valid_until,
      to_char(q.valid_from AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS quantity_valid_from,
      to_char(q.valid_until AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS quantity_valid_until
      FROM hosted_crypto_sale_permissions s JOIN hosted_execution_terms q ON q.asset_id=s.asset_id AND q.revision=s.quantity_terms_revision
      WHERE s.coin=$1 AND s.quantity_rules_apply_to_sales`, [coin]);
    return (rows[0] as PlanTerms | undefined) ?? null;
  }
  async read(coin: string) {
    const rows = await this.query(`SELECT s.coin,s.version::text,p.plan,
      coalesce((SELECT jsonb_agg(h.plan ORDER BY h.accepted_at,h.plan_id) FROM hosted_crypto_plan_history h WHERE h.coin=s.coin),'[]'::jsonb) AS history
      FROM hosted_crypto_plan_state s LEFT JOIN hosted_crypto_plan_history p ON p.plan_id=s.current_plan_id WHERE s.coin=$1`, [coin]);
    if (!rows.length) throw Error('crypto_plan_storage_unavailable');
    return { state: 'ready', ...rows[0], terms: await this.terms(coin) };
  }
  async prior(request: PlanRequest) {
    const rows = await this.query('SELECT request=$2::jsonb AS same,result FROM hosted_crypto_plan_operations WHERE operation_id=$1', [request.operation_id, JSON.stringify(request)]);
    return rows[0] ? { same: rows[0].same === true, result: rows[0].result } : null;
  }
  async context(coin: string, templates: Templates) {
    const [snapshot, terms, market] = await Promise.all([this.snapshot(), this.terms(coin), this.market(coin, templates)]);
    return { snapshot, terms, market };
  }
  async commit(request: PlanRequest, plan: Record<string, any>) {
    const rows = await this.query('SELECT hosted_accept_crypto_plan($1::jsonb,$2::jsonb) AS result', [JSON.stringify(request), JSON.stringify(plan)]);
    return rows[0].result;
  }
}
export function neonCryptoPlans(url: string) {
  const sql = neon(url);
  return cryptoPlans(new NeonCryptoPlanStore((query, params) => sql.query(query, params),
    () => neonSnapshotStore(url).readAccepted(), (coin, templates) => previewCryptoLevels({ coin, templates }, neonCryptoMarketReader(url))));
}
