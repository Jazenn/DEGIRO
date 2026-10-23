import { expect, test } from 'vitest';
import { workerApplication } from './worker';
import { databaseTransport, env, login } from './auth-test-support';

test('Worker entry shares one in-flight current refresh across concurrent owner requests', async () => {
  let reads = 0, release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let authentications = 0, authorized!: () => void;
  const bothAuthorized = new Promise<void>(resolve => { authorized = resolve; });
  const database = databaseTransport();
  const app = workerApplication({ authQuery: async (sql, params) => {
    const result = await database(sql, params);
    if (sql.startsWith('SELECT s.google_sub') && ++authentications === 2) authorized();
    return result;
  }, refreshStore: () => ({
    read: async () => { reads++; await gate; return null; }, publish: async () => false,
  }) });
  const headers = { Cookie: (await login()).session!, Origin: env.APP_ORIGIN };
  const request = () => app(new Request(env.APP_ORIGIN+'/api/refresh', { method: 'POST', headers }), env);
  const first = request(), second = request();
  await bothAuthorized;
  await new Promise(resolve => setTimeout(resolve, 0));
  release();
  const responses = await Promise.all([first, second]);
  expect(reads).toBe(1);
  expect(await responses[0].json()).toEqual(await responses[1].json());
});

