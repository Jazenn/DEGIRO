import { expect, test } from 'vitest';
import { createApplication } from './application';
import { previewCryptoLevels } from './crypto-market-store';
import { env, databaseTransport, login } from './auth-test-support';

test('owner-only market previews do not require private holdings or accepted financial eligibility', async () => {
  const app = createApplication({ authQuery: databaseTransport(), readAccepted: async () => { throw Error('private ledger must not be read'); },
    cryptoLevels: value => previewCryptoLevels(value, { read: async () => null }, '2026-10-23T12:00:00Z') });
  const request = (headers = {}) => new Request(env.APP_ORIGIN + '/api/crypto/levels', {
    method: 'POST', headers: { Origin: env.APP_ORIGIN, ...headers }, body: JSON.stringify({ coin: 'BTC-EUR' }) });
  expect((await app(request(), env)).status).toBe(401);
  const cookie = (await login()).session!;
  const response = await app(request({ Cookie: cookie }), env);
  expect(response.status).toBe(200);
  expect(response.headers.get('cache-control')).toBe('private, no-store');
  const result = await response.json();
  expect(result.state).toBe('paused');
  expect(result.missing_days).toHaveLength(365);
  expect(result.purchase).toEqual([]);
  expect((await app(new Request(env.APP_ORIGIN + '/api/crypto/levels', { method: 'POST', headers: { Cookie: cookie } }), env)).status).toBe(403);
});

test('market-version conflicts reject stale previews and malformed percentile templates are invalid', async () => {
  const reader = { read: async () => ({ coin: 'ETH-EUR', version: 'new', observations: {}, attempted_at: '2026-10-23T00:23:00Z', diagnostics: [] }) };
  expect(await previewCryptoLevels({ coin: 'ETH-EUR', market_version: 'old' }, reader)).toEqual({ state: 'stale', reason: 'market_history_changed' });
  await expect(previewCryptoLevels({ coin: 'ETH-EUR', templates: { purchase: ['101','20','10'], sale: ['75','90','95'] } }, reader)).rejects.toThrow('invalid_percentiles');
});
