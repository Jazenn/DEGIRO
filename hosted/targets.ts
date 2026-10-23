import { neon } from '@neondatabase/serverless';
export interface Targets { version: string; targets: { asset_id: string; target_pct: string }[] }
export class TargetsStore {
  constructor(private query: (sql: string, params: unknown[]) => Promise<Record<string, unknown>[]>) {}
  async read(): Promise<Targets> {
    const rows = await this.query('SELECT version::text, targets FROM hosted_targets WHERE singleton = true', []);
    return (rows[0] as unknown as Targets) || { version: '0', targets: [] };
  }
  async save(value: unknown) {
    const input = value as Record<string, unknown>;
    if (!input || typeof input.operation_id !== 'string' || !/^[\w-]{8,100}$/.test(input.operation_id)
      || typeof input.expected_version !== 'string' || !/^\d{1,18}$/.test(input.expected_version)
      || !Array.isArray(input.targets) || !input.targets.length || input.targets.length > 100) throw Error('invalid_targets');
    let total = 0;
    const ids = new Set<string>();
    for (const row of input.targets) {
      if (!row || typeof row.asset_id !== 'string' || !/^[\w.:-]{1,100}$/.test(row.asset_id) || ids.has(row.asset_id)
        || typeof row.target_pct !== 'string' || !/^\d{1,3}(?:\.\d{1,2})?$/.test(row.target_pct)) throw Error('invalid_targets');
      const points = Math.round(Number(row.target_pct) * 100);
      if (points > 10000) throw Error('invalid_targets');
      ids.add(row.asset_id); total += points;
    }
    if (total !== 10000) throw Error('invalid_targets');
    const rows = await this.query('SELECT hosted_save_targets($1, $2::bigint, $3::jsonb) AS result',
      [input.operation_id, input.expected_version, JSON.stringify(input.targets)]);
    return rows[0].result as { state: string; current: Targets };
  }
}
export function neonTargetsStore(url: string) {
  const sql = neon(url);
  return new TargetsStore(async (query, params) => await sql.query(query, params));
}
