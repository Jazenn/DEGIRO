import { expect, test } from 'vitest';
import { createApplication } from './application';
import { databaseTransport, env, login } from './auth-test-support';
import { TargetsStore } from './targets';

test('owner saves validated versioned targets, rejects stale edits and can safely retry', async () => {
  let state = { version: '0', targets: [] as unknown[] };
  const operations = new Map<string, { body: string; result: unknown }>();
  const store = new TargetsStore(async (sql, params) => {
    if (sql.startsWith('SELECT version')) return [state];
    const [id, version, targets] = params as string[];
    const body = JSON.stringify([version, targets]);
    const previous = operations.get(id);
    if (previous) return [{ result: previous.body === body ? previous.result : { state: 'conflict', current: state } }];
    const result = version !== state.version ? { state: 'conflict', current: state } :
      { state: 'saved', current: state = { version: String(Number(version) + 1), targets: JSON.parse(targets) } };
    operations.set(id, { body, result });
    return [{ result }];
  });
  const app = createApplication({ readAccepted: async () => null, authQuery: databaseTransport(), targets: () => store });
  const cookie = (await login()).session!;
  const call = (body: unknown, authenticated = true, origin = env.APP_ORIGIN) => app(new Request(env.APP_ORIGIN + '/api/targets', {
    method: 'PUT', headers: { Cookie: authenticated ? cookie : '', Origin: origin, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }), env);
  const edit = { operation_id: 'device-a-save-1', expected_version: '0', targets: [{ asset_id: 'ETF', target_pct: '60' }, { asset_id: 'BTC', target_pct: '40' }] };
  expect((await call(edit, false)).status).toBe(401);
  expect((await call(edit, true, 'https://wrong.test')).status).toBe(403);
  expect((await call({ ...edit, targets: [{ asset_id: 'ETF', target_pct: '99' }] })).status).toBe(400);
  expect(await (await call(edit)).json()).toEqual({ state: 'saved', current: { version: '1', targets: edit.targets } });
  expect(await (await call(edit)).json()).toEqual({ state: 'saved', current: { version: '1', targets: edit.targets } });
  const stale = await call({ ...edit, operation_id: 'device-b-save-1' });
  expect(stale.status).toBe(409);
  expect(await stale.json()).toEqual({ state: 'conflict', current: { version: '1', targets: edit.targets } });
  const read = await app(new Request(env.APP_ORIGIN + '/api/targets', { headers: { Cookie: cookie } }), env);
  expect(await read.json()).toEqual({ version: '1', targets: edit.targets });
});
