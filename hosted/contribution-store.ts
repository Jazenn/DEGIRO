import { neon } from '@neondatabase/serverless';
import { validReadModel } from './read-model';
import { planContribution, type ExecutionTerms } from './contribution';
import type { AcceptedSnapshot } from './application';
import type { Targets } from './targets';
export interface ContributionInput { snapshot: AcceptedSnapshot; settings: Targets; terms: ExecutionTerms[] }
export interface ContributionStore { read(): Promise<ContributionInput | null> }
export function createContribution(store: ContributionStore, clock = () => Date.now()) {
  return async (value: unknown) => {
    const input = value as Record<string, unknown>;
    if (!input || typeof input.generation_id !== 'string' || typeof input.settings_version !== 'string') throw Error('invalid_request');
    const current = await store.read();
    if (!current) return { state: 'stale', reason: 'no_accepted_snapshot' };
    if (current.snapshot.generation_id !== input.generation_id || current.settings.version !== input.settings_version
      || current.snapshot.read_model.settings_version !== current.settings.version)
      return { state: 'stale', reason: 'valuation_or_targets_changed_refresh_required', generation_id: current.snapshot.generation_id, settings_version: current.settings.version };
    return { ...planContribution(current.snapshot.read_model, current.settings, current.terms, input.budget_eur, new Date(clock()).toISOString()),
      generation_id: current.snapshot.generation_id, ledger_version: current.snapshot.read_model.ledger_version,
      settings_version: current.settings.version, calculation_version: current.snapshot.read_model.calculation_version, valuation_cutoff: current.snapshot.read_model.cutoff };
  };
}
export function neonContributionStore(url: string): ContributionStore {
  const sql = neon(url);
  return { async read() {
    const rows = await sql.query(`SELECT g.generation_id, to_char(g.published_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS published_at, g.data_classification, g.read_model, t.version::text AS settings_version, t.targets,
      (SELECT coalesce(jsonb_agg(jsonb_build_object('asset_id',asset_id,'revision',revision,'quantity_step',quantity_step::text,
        'minimum_quantity',minimum_quantity::text,'minimum_notional_eur',minimum_notional_eur::text,'fixed_fee_eur',fixed_fee_eur::text,
        'fee_rate_pct',fee_rate_pct::text,'minimum_fee_eur',minimum_fee_eur::text,'fee_status',fee_status,'evidence',evidence,
        'valid_from',to_char(valid_from AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'valid_until',to_char(valid_until AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))), '[]'::jsonb) FROM hosted_execution_terms) AS terms
      FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id) CROSS JOIN hosted_targets t
      WHERE p.singleton AND t.singleton`, []);
    if (!rows.length) return null;
    const row = rows[0];
    if (!validReadModel(row.read_model) || !Array.isArray(row.terms) || !Array.isArray(row.targets)) throw Error('invalid_snapshot');
    return { snapshot: { generation_id: row.generation_id, published_at: row.published_at, data_classification: row.data_classification, read_model: row.read_model },
      settings: { version: row.settings_version, targets: row.targets }, terms: row.terms } as ContributionInput;
  } };
}

