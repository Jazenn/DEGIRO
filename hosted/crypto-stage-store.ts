import { neon } from '@neondatabase/serverless';
import { reviewReachedStages, type Progress } from './crypto-stage-review';
import { validReadModel } from './read-model';
import { validCoin } from './crypto-plan';
export interface StageContext { snapshot: any; state: any; fees: any; progress?: Progress }
export interface StageReader { read(coin: string): Promise<StageContext | null> }
export async function previewStageReview(value: unknown, store: StageReader, now = new Date().toISOString()) {
  const input = value as Record<string, unknown>;
  if (!input || !validCoin(input.coin) || (input.generation_id !== undefined && typeof input.generation_id !== 'string')
      || (input.plan_version !== undefined && typeof input.plan_version !== 'string')) throw Error('invalid_stage_review');
  const context = await store.read(input.coin);
  if (!context) return { state: 'unavailable', reason: 'accepted_plan_storage_unavailable', stages: [] };
  if ((input.generation_id !== undefined && input.generation_id !== context.snapshot?.generation_id)
      || (input.plan_version !== undefined && input.plan_version !== context.state.version))
    return { state: 'conflict', reason: 'snapshot_or_plan_changed', stages: [] };
  return { coin: input.coin, ...reviewReachedStages(context.snapshot, context.state, context.fees, now, context.progress) };
}
export function neonStageReviewReader(url: string): StageReader {
  const sql = neon(url);
  return { async read(coin) {
    // One MVCC statement binds plan, accepted generation, sale permission and cost revision.
    const rows = await sql.query(`SELECT s.version::text AS plan_version,h.plan,g.generation_id,g.read_model,
      jsonb_build_object('asset_id',p.asset_id,'revision',f.revision,'permission_revision',p.revision,
        'quantity_terms_revision',q.revision,'fixed_fee_eur',f.fixed_fee_eur::text,'fee_rate_pct',f.fee_rate_pct::text,
        'minimum_fee_eur',f.minimum_fee_eur::text,'spread_allowance_pct',f.spread_allowance_pct::text,
        'fee_status',f.fee_status,'all_costs_reviewed',f.all_costs_reviewed,'evidence',f.evidence,'spread_evidence',f.spread_evidence,
        'valid_from',to_char(f.valid_from AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'valid_until',to_char(f.valid_until AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'permission_valid_from',to_char(p.valid_from AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'permission_valid_until',to_char(p.valid_until AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'quantity_valid_from',to_char(q.valid_from AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'quantity_valid_until',to_char(q.valid_until AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')) AS fees
      FROM hosted_crypto_plan_state s LEFT JOIN hosted_crypto_plan_history h ON h.plan_id=s.current_plan_id
      LEFT JOIN hosted_snapshot_pointer ptr ON ptr.singleton=true LEFT JOIN hosted_snapshot_generations g ON g.generation_id=ptr.generation_id
      LEFT JOIN hosted_crypto_sale_permissions p ON p.coin=s.coin AND p.quantity_rules_apply_to_sales
      LEFT JOIN hosted_execution_terms q ON q.asset_id=p.asset_id AND q.revision=p.quantity_terms_revision
      LEFT JOIN hosted_crypto_sale_costs f ON f.coin=p.coin AND f.permission_revision=p.revision WHERE s.coin=$1`, [coin]);
    const row = rows[0];
    if (!row) return null;
    if (row.read_model && !validReadModel(row.read_model)) throw Error('invalid_snapshot');
    // #58 extends this same coherent read with durable execution/report progress.
    return { snapshot: row.generation_id ? { generation_id: row.generation_id, read_model: row.read_model } : null,
      state: { version: row.plan_version, plan: row.plan }, fees: row.fees };
  } };
}
