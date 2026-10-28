import { neon } from '@neondatabase/serverless';
import { validReadModel, timestamp } from './read-model';
import type { RefreshInput, RefreshStore } from './refresh';
type Query = (query: string, params: unknown[], signal: AbortSignal) => Promise<Record<string, any>[]>;
export function valuationStore(query: Query): RefreshStore {
  return {
    async read(signal) {
      const rows = await query(`SELECT g.generation_id, to_char(g.published_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS published_at, g.data_classification, g.read_model,
        t.version::text AS rebalancing_targets_version, t.targets,
        (SELECT coalesce(jsonb_agg(symbol),'[]'::jsonb) FROM hosted_contribution_assets WHERE verified_at <= now()) AS planning_symbols,
        (SELECT coalesce(jsonb_agg(jsonb_build_object('symbol', symbol, 'provider', provider, 'provider_symbol', provider_symbol, 'evidence', evidence)), '[]'::jsonb) FROM hosted_quote_mappings) AS mappings
        FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id)
        CROSS JOIN hosted_targets t WHERE p.singleton AND t.singleton`, [], signal);
      if (!rows.length) return null;
      const row = rows[0];
      if (!validReadModel(row.read_model) || !timestamp(row.published_at) || !['synthetic','private'].includes(row.data_classification)
        || typeof row.generation_id !== 'string' || typeof row.rebalancing_targets_version !== 'string' || !/^\d+$/.test(row.rebalancing_targets_version)
        || !Array.isArray(row.targets) || !Array.isArray(row.mappings)
        || (row.planning_symbols !== undefined && (!Array.isArray(row.planning_symbols) || !row.planning_symbols.every((symbol: unknown) => typeof symbol === 'string' && symbol.length > 0)))
        || !row.targets.every((target: any) => target && typeof target.asset_id === 'string' && typeof target.target_pct === 'string')
        || !row.mappings.every((mapping: any) => mapping && typeof mapping.symbol === 'string' && typeof mapping.evidence === 'string' && mapping.evidence.length > 0
          && ['binance','yahoo','kraken'].includes(mapping.provider) && typeof mapping.provider_symbol === 'string')) throw Error('invalid_snapshot');
      return { snapshot: { generation_id: row.generation_id, published_at: row.published_at, data_classification: row.data_classification, read_model: row.read_model },
        settings: { version: row.rebalancing_targets_version, targets: row.targets }, mappings: row.mappings, planning_symbols: row.planning_symbols ?? [] } as RefreshInput;
    },
    async publish(input, model, generation, deadline, signal) {
      if (!validReadModel(model)) throw Error('invalid_valuation');
      const rows = await query('SELECT hosted_publish_valuation($1,$2,$3::bigint,$4::jsonb,$5::timestamptz) AS published',
        [generation, input.snapshot.generation_id, input.settings.version, JSON.stringify(model), deadline], signal);
      return rows[0]?.published === true;
    },
  };
}


export function neonRefreshStore(url: string): RefreshStore {
  const sql = neon(url);
  return valuationStore((query, params, signal) => sql.query(query, params, { fetchOptions: { signal } }));
}
