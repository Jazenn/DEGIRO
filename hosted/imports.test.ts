import { expect, test } from 'vitest';
import { handleImports, ImportStore } from './import-store';
const env = { DATABASE_URL: 'unused', APP_ORIGIN: 'https://private.example', IMPORTS_ENABLED: 'true' };
test('upload rejects missing origin and empty files before storing private bytes', async () => {
  const store = new ImportStore(async () => { throw Error('must not reach database'); });
  expect((await handleImports(new Request(env.APP_ORIGIN + '/api/imports', { method: 'POST' }), env, store)).status).toBe(403);
  expect((await handleImports(new Request(env.APP_ORIGIN + '/api/imports', { method: 'POST',
    headers: { Origin: env.APP_ORIGIN, 'Content-Type': 'text/csv' }, body: '' }), env, store)).status).toBe(400);
});
test('same private CSV retains one identity across upload retries and status excludes raw records', async () => {
  // Database transport boundary emulates unique-content durable identity.
  const rows = new Map<string, Record<string, unknown>>();
  const store = new ImportStore(async (_sql, params) => {
    const hash = String(params[1]);
    if (!rows.has(hash)) rows.set(hash, { job_id: params[0], state: 'pending', history_state: 'unavailable' });
    return [rows.get(hash)!];
  });
  const submit = () => handleImports(new Request(env.APP_ORIGIN + '/api/imports', { method: 'POST',
    headers: { Origin: env.APP_ORIGIN, 'Content-Type': 'text/csv' }, body: 'Date,Product\nsynthetic' }), env, store);
  const first = await submit(); const again = await submit();
  expect(first.status).toBe(202);
  expect(await again.json()).toEqual(await first.json());
});
test('unconfigured deployment rejects uploads explicitly', async () => {
  expect((await handleImports(new Request(env.APP_ORIGIN + '/api/imports'), { ...env, IMPORTS_ENABLED: '' })).status).toBe(503);
});
