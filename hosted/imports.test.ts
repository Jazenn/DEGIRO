import { expect, test } from 'vitest';
import { handleImports, ImportStore } from './import-store';
import { createApplication } from './application';
import { env as authEnvironment, databaseTransport, login } from './auth-test-support';
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

test('authenticated import routes enforce owner session and retain private no-store headers', async () => {
  const store = new ImportStore(async () => [{ job_id: 'synthetic', state: 'pending', history_state: 'unavailable' }]);
  const app = createApplication({ readAccepted: async () => null, authQuery: databaseTransport(),
    handleImports: (request, environment) => handleImports(request, environment, store) });
  const environment = { ...authEnvironment, IMPORTS_ENABLED: 'true' };
  for (const path of ['/api/imports', '/api/imports/synthetic/retry']) {
    expect((await app(new Request(environment.APP_ORIGIN + path, { method: 'POST' }), environment)).status).toBe(401);
  }
  const cookie = (await login()).session!;
  const response = await app(new Request(environment.APP_ORIGIN + '/api/imports', { headers: { Cookie: cookie } }), environment);
  expect(response.status).toBe(200);
  expect(response.headers.get('cache-control')).toBe('private, no-store');
  expect(await response.json()).toEqual({ jobs: [{ job_id: 'synthetic', state: 'pending', history_state: 'unavailable' }] });
  expect((await app(new Request(environment.APP_ORIGIN + '/api/imports', { method: 'POST', headers: { Cookie: cookie } }), environment)).status).toBe(403);
});

test('maximum supported UTF-8 upload preserves BOM and bytes without per-byte encoding', async () => {
  const content = new Uint8Array(5 * 1024 * 1024);
  content.fill(65); content[0] = 239; content[1] = 187; content[2] = 191;
  const store = new ImportStore(async (_sql, params) => {
    const decoded = Buffer.from(String(params[2]), 'utf8');
    expect(decoded.length).toBe(content.length);
    expect(decoded[0]).toBe(239);
    expect(decoded[decoded.length - 1]).toBe(65);
    return [{ state: 'pending' }];
  });
  expect(await store.submit(content)).toEqual([{ state: 'pending' }]);
  await expect(store.submit(new Uint8Array(content.length + 1))).rejects.toThrow('invalid_upload_size');
  await expect(store.submit(new Uint8Array([255]))).rejects.toThrow('invalid_upload_encoding');
});
