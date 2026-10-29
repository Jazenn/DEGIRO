import { neon } from '@neondatabase/serverless';
import type { AcceptedSnapshot, SnapshotReader } from './application';
import { validReadModel, timestamp } from './read-model.ts';

type Query = (sql: string, params: unknown[]) => Promise<Record<string, unknown>[]>;
export class NeonSnapshotStore implements SnapshotReader {
  private query: Query;
  constructor(query: Query) { this.query = query; }
  async readAccepted(): Promise<AcceptedSnapshot | null> {
    // One statement observes a coherent pointer + immutable generation under MVCC.
    const rows = await this.query(`SELECT g.generation_id,
      to_char(g.published_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS published_at,
      g.data_classification, g.read_model - 'portfolio_history' AS read_model
      FROM hosted_snapshot_pointer p LEFT JOIN hosted_snapshot_generations g
        ON g.generation_id = p.generation_id WHERE p.singleton = true`, []);
    if (!rows.length) return null;
    const row = rows[0];
    if (!row.generation_id || !timestamp(row.published_at) || !validReadModel(row.read_model)
        || !['synthetic', 'private'].includes(String(row.data_classification))) throw Error('Invalid accepted Snapshot');
    return { generation_id: String(row.generation_id), published_at: String(row.published_at),
      data_classification: row.data_classification as 'synthetic' | 'private', read_model: row.read_model };
  }
}
export function neonSnapshotStore(databaseUrl: string): SnapshotReader {
  const sql = neon(databaseUrl);
  return new NeonSnapshotStore(async (query, params) => await sql.query(query, params));
}
