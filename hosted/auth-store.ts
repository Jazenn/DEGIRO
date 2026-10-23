import { neon } from '@neondatabase/serverless';

export type AuthQuery = (sql: string, params: unknown[]) => Promise<Record<string, unknown>[]>;
export function authQuery(databaseUrl: string): AuthQuery {
  const sql = neon(databaseUrl);
  return async (query, params) => await sql.query(query, params);
}
export async function tokenHash(token: string) {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token)));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}
export class AuthStore {
  constructor(private query: AuthQuery) {}
  async bindOwner(sub: string, email: string) {
    // Conflict never overwrites the first verified owner's Google subject.
    await this.query('INSERT INTO hosted_owner_identity (singleton, google_sub, owner_email) VALUES (true, $1, $2) ON CONFLICT (singleton) DO NOTHING', [sub, email]);
    const rows = await this.query('SELECT google_sub, owner_email FROM hosted_owner_identity WHERE singleton = true', []);
    return rows[0]?.google_sub === sub && rows[0]?.owner_email === email;
  }
  async createSession(token: string, sub: string, email: string) {
    await this.query("INSERT INTO hosted_sessions (token_hash, google_sub, owner_email, expires_at) VALUES ($1, $2, $3, now() + interval '30 days')", [await tokenHash(token), sub, email]);
  }
  async ownerSession(token: string, email: string) {
    const rows = await this.query(`SELECT s.google_sub FROM hosted_sessions s JOIN hosted_owner_identity o
      ON o.google_sub = s.google_sub AND o.owner_email = s.owner_email
      WHERE s.token_hash = $1 AND s.owner_email = $2 AND s.expires_at > now()`, [await tokenHash(token), email]);
    return rows.length === 1;
  }
  async revokeSession(token: string) {
    await this.query('DELETE FROM hosted_sessions WHERE token_hash = $1', [await tokenHash(token)]);
  }
}
