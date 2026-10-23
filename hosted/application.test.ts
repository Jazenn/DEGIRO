import { generateKeyPair, exportJWK, SignJWT, type JSONWebKeySet } from 'jose';
import { beforeAll, expect, test } from 'vitest';
import { createApplication, type Environment } from './application';
import { readFile } from 'node:fs/promises';
import { NeonSnapshotStore } from './snapshot-store';

const issuer = 'https://synthetic.cloudflareaccess.com';
let keys: Awaited<ReturnType<typeof generateKeyPair>>;
let jwks: JSONWebKeySet;
beforeAll(async () => {
  keys = await generateKeyPair('RS256', { extractable: true });
  jwks = { keys: [{ ...await exportJWK(keys.publicKey), kid: 'synthetic', alg: 'RS256' }] };
});
const env: Environment = {
  ACCESS_ISSUER: issuer, ACCESS_AUDIENCE: 'synthetic-audience', OWNER_EMAIL: 'owner@example.test',
  DATABASE_URL: 'postgres://synthetic', APP_ORIGIN: 'https://portfolio.example.test',
  ASSETS: { fetch: async () => new Response('<h1>Private Snapshot</h1>') },
};
async function token(claims: Record<string, unknown> = {}, signingKeys = keys) {
  return new SignJWT({ email: 'owner@example.test', ...claims }).setProtectedHeader({ alg: 'RS256', kid: 'synthetic' })
    .setIssuer(issuer).setAudience('synthetic-audience').setIssuedAt().setExpirationTime('1h').sign(signingKeys.privateKey);
}
function app(read: (env: Environment) => Promise<any> = async () => null) {
  return createApplication({ readAccepted: read, jwks: async () => jwks });
}
test('every private route rejects an unauthenticated request before reading assets or data', async () => {
  for (const path of ['/', '/index.html', '/app.js', '/api/snapshot', '/versions/old', '/preview']) {
    const response = await app()(new Request(env.APP_ORIGIN + path), env);
    expect(response.status).toBe(401);
    expect(response.headers.get('cache-control')).toBe('private, no-store');
  }
});
test('cryptographically authenticated owner can read persisted decimal strings and unavailable values intact', async () => {
  const snapshot = { generation_id: 'generation-1', published_at: '2026-10-22T00:00:00Z', data_classification: 'synthetic',
    read_model: { ledger_version: 'ledger-1', settings_version: 'settings-1', calculation_version: 'decimal-accounting-v1',
      ledger: { market_value_eur: '1100.0000000000000001', net_gain_eur: null }, diagnostics: ['missing_cost'] } };
  const response = await app(async () => snapshot)(new Request(env.APP_ORIGIN + '/api/snapshot', {
    headers: { 'Cf-Access-Jwt-Assertion': await token() },
  }), env);
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ state: 'ready', snapshot });
});
test('invalid signatures and claims cannot authorize alternate routes, assets or writes', async () => {
  const stranger = await generateKeyPair('RS256');
  const invalid = [await token({}, stranger), await token({ iss: 'https://attacker.test' }),
    await new SignJWT({ email: 'owner@example.test' }).setProtectedHeader({ alg: 'RS256', kid: 'synthetic' })
      .setIssuer(issuer).setAudience('wrong').setIssuedAt().setExpirationTime('1h').sign(keys.privateKey),
    await new SignJWT({ email: 'owner@example.test' }).setProtectedHeader({ alg: 'RS256', kid: 'synthetic' })
      .setIssuer(issuer).setAudience('synthetic-audience').setIssuedAt().setExpirationTime(1).sign(keys.privateKey)];
  // token() sets issuer after payload; construct a wrong issuer explicitly.
  invalid[1] = await new SignJWT({ email: 'owner@example.test' }).setProtectedHeader({ alg: 'RS256', kid: 'synthetic' })
    .setIssuer('https://attacker.test').setAudience('synthetic-audience').setIssuedAt().setExpirationTime('1h').sign(keys.privateKey);
  for (const assertion of invalid) {
    for (const path of ['/api/snapshot', '/app.js', '/preview/version']) {
      expect((await app()(new Request(env.APP_ORIGIN + path, { headers: { 'Cf-Access-Jwt-Assertion': assertion } }), env)).status).toBe(401);
    }
  }
  expect((await app()(new Request(env.APP_ORIGIN + '/api/snapshot', { method: 'POST', headers: { 'Cf-Access-Authenticated-User-Email': 'owner@example.test' } }), env)).status).toBe(401);
  expect((await app()(new Request(env.APP_ORIGIN + '/', { headers: { 'Cf-Access-Jwt-Assertion': await token({ email: 'other@example.test' }) } }), env)).status).toBe(403);
});
test('empty and storage failure remain explicit and never substitute synthetic values', async () => {
  const request = new Request(env.APP_ORIGIN + '/api/snapshot', { headers: { 'Cf-Access-Jwt-Assertion': await token() } });
  expect(await (await app()(request, env)).json()).toEqual({ state: 'empty' });
  const failed = await app(async () => { throw Error('secret database connection'); })(request, env);
  expect(failed.status).toBe(503);
  expect(await failed.json()).toEqual({ state: 'error', error: 'snapshot_unavailable' });
  expect((await app()(request, { ...env, OWNER_EMAIL: '' })).status).toBe(503);
});
test('persisted canonical Snapshot is returned intact and a broken accepted generation is an error', async () => {
  const model = JSON.parse(await readFile(new URL('./synthetic.fixture', import.meta.url), 'utf8'));
  const row = { generation_id: 'synthetic-1', published_at: '2026-10-22T00:00:00Z', data_classification: 'synthetic', read_model: model };
  // SQL transport is the database system boundary. Live verification uses this same store.
  const store = new NeonSnapshotStore(async () => [row]);
  const request = new Request(env.APP_ORIGIN + '/api/snapshot', { headers: { 'Cf-Access-Jwt-Assertion': await token() } });
  const response = await app(() => store.readAccepted())(request, env);
  expect(await response.json()).toEqual({ state: 'ready', snapshot: row });
  const corrupt = new NeonSnapshotStore(async () => [{ ...row, read_model: { ...model, ledger: null } }]);
  expect((await app(() => corrupt.readAccepted())(request, env)).status).toBe(503);
});
test('missing required canonical values or malformed decimals never appear as a ready generation', async () => {
  const original = JSON.parse(await readFile(new URL('./synthetic.fixture', import.meta.url), 'utf8'));
  const request = new Request(env.APP_ORIGIN + '/api/snapshot', { headers: { 'Cf-Access-Jwt-Assertion': await token() } });
  const edits = [
    (model: any) => { delete model.ledger.equity_eur; },
    (model: any) => { model.ledger.cash_balance_eur = 'NaN'; },
    (model: any) => { model.ledger.positions[0].quantity = 1; },
    (model: any) => { delete model.ledger.positions[0].lots[0].cost_eur; },
    (model: any) => { delete model.observed_prices.SYNTHETIC.observed_at; },
    (model: any) => { model.cutoff = 'yesterday'; },
    (model: any) => { model.settings_version = ''; },
  ];
  for (const edit of edits) {
    const model = structuredClone(original); edit(model);
    const store = new NeonSnapshotStore(async () => [{ generation_id: 'broken', published_at: '2026-10-22T00:00:00Z', data_classification: 'synthetic', read_model: model }]);
    expect((await app(() => store.readAccepted())(request, env)).status).toBe(503);
  }
});
test('HEAD responses have no body and owner-only write routes require the configured origin', async () => {
  const headers = { 'Cf-Access-Jwt-Assertion': await token() };
  const head = await app()(new Request(env.APP_ORIGIN + '/api/snapshot', { method: 'HEAD', headers }), env);
  expect(await head.text()).toBe('');
  expect((await app()(new Request(env.APP_ORIGIN + '/api/snapshot', { method: 'POST', headers }), env)).status).toBe(403);
  expect((await app()(new Request(env.APP_ORIGIN + '/api/snapshot', { method: 'POST', headers: { ...headers, Origin: env.APP_ORIGIN } }), env)).status).toBe(405);
  expect((await app()(new Request(env.APP_ORIGIN + '/app.js', { headers }), env)).headers.get('cache-control')).toBe('private, no-store');
});
