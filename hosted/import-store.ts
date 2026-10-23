import { neon } from '@neondatabase/serverless';

export type ImportQuery = (query: string, params: unknown[]) => Promise<Record<string, unknown>[]>;
const columns = 'job_id, state, history_state, attempts, diagnostics, generation_id, created_at, updated_at';
const maxBytes = 5 * 1024 * 1024;
export class ImportStore {
  constructor(private query: ImportQuery) {}
  async list() {
    return this.query(`SELECT ${columns} FROM hosted_import_jobs ORDER BY created_at DESC LIMIT 30`, []);
  }
  async submit(content: Uint8Array) {
    if (!content.length || content.length > maxBytes) throw Error('invalid_upload_size');
    const digest = await crypto.subtle.digest('SHA-256', Uint8Array.from(content).buffer);
    const hash = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
    const pieces: string[] = [];
    for (let offset = 0; offset < content.length; offset += 24576)
      pieces.push(btoa(String.fromCharCode(...content.subarray(offset, offset + 24576))));
    const encoded = pieces.join('');
    // One statement makes repeated submissions share the same durable identity.
    return this.query(`INSERT INTO hosted_import_jobs(job_id, content_hash, csv_content)
      VALUES($1,$2,decode($3,'base64')) ON CONFLICT(content_hash) DO UPDATE SET content_hash=excluded.content_hash
      RETURNING ${columns}`, [crypto.randomUUID(), hash, encoded]);
  }
  async retry(id: string) {
    // Processing jobs can be recovered only after the runner's ten-minute timeout.
    return this.query(`UPDATE hosted_import_jobs SET state='pending', diagnostics='[]', updated_at=now()
      WHERE job_id=$1 AND (state='failed' OR (state='processing' AND updated_at < now()-interval '15 minutes'))
      RETURNING ${columns}`, [id]);
  }
}

interface ImportEnvironment { DATABASE_URL: string; APP_ORIGIN: string; IMPORTS_ENABLED?: string }
export async function handleImports(request: Request, env: ImportEnvironment, store?: ImportStore): Promise<Response> {
  if (env.IMPORTS_ENABLED !== 'true') return Response.json({ error: 'imports_not_configured' }, { status: 503 });
  const path = new URL(request.url).pathname;
  if (!['GET', 'HEAD'].includes(request.method) && request.headers.get('Origin') !== env.APP_ORIGIN)
    return Response.json({ error: 'origin_rejected' }, { status: 403 });
  const sql = store ? null : neon(env.DATABASE_URL);
  const repository = store || new ImportStore(async (query, params) => await sql!.query(query, params));
  try {
    if (['GET', 'HEAD'].includes(request.method) && path === '/api/imports')
      return Response.json({ jobs: await repository.list() });
    if (request.method === 'POST' && path === '/api/imports') {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'text/csv')
        return Response.json({ error: 'csv_required' }, { status: 415 });
      // Bound streaming bodies too: do not allocate an unbounded arrayBuffer.
      const reader = request.body?.getReader();
      const chunks: Uint8Array[] = []; let size = 0;
      if (reader) while (true) {
        const part = await reader.read(); if (part.done) break;
        size += part.value.length;
        if (size > maxBytes) { await reader.cancel(); return Response.json({ error: 'upload_too_large' }, { status: 413 }); }
        chunks.push(part.value);
      }
      if (!size) return Response.json({ error: 'empty_upload' }, { status: 400 });
      const content = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { content.set(chunk, offset); offset += chunk.length; }
      return Response.json({ jobs: await repository.submit(content) }, { status: 202 });
    }
    const retry = /^\/api\/imports\/([a-zA-Z0-9-]+)\/retry$/.exec(path);
    if (request.method === 'POST' && retry) {
      const jobs = await repository.retry(retry[1]);
      return Response.json({ jobs }, { status: jobs.length ? 202 : 409 });
    }
    return Response.json({ error: 'method_not_allowed' }, { status: 405 });
  } catch { return Response.json({ error: 'imports_unavailable' }, { status: 503 }); }
}
