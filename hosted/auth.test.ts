import { expect, test, vi } from 'vitest';
import { createApplication } from './application';
import { env, login, application, databaseTransport, type DatabaseState } from './auth-test-support';

test('visitor sees only the public sign in page and is sent to Google with protected authorization parameters', async () => {
  const app = createApplication({ readAccepted: async () => null });
  const page = await app(new Request(env.APP_ORIGIN + '/login'), env);
  expect(page.status).toBe(200);
  expect(await page.text()).toContain('Sign in with Google');
  const start = await app(new Request(env.APP_ORIGIN + '/auth/login'), env);
  expect(start.status).toBe(302);
  const google = new URL(start.headers.get('location')!);
  expect(google.origin).toBe('https://accounts.google.com');
  expect(google.searchParams.get('scope')).toBe('openid email');
  expect(google.searchParams.get('redirect_uri')).toBe(env.APP_ORIGIN + '/auth/callback');
  expect(google.searchParams.get('code_challenge_method')).toBe('S256');
  expect(google.searchParams.get('state')).toBeTruthy();
  expect(google.searchParams.get('nonce')).toBeTruthy();
  expect(start.headers.get('set-cookie')).toContain('HttpOnly; Secure; SameSite=Lax');
});


test('callback without a matching browser login transaction cannot create a session', async () => {
  const app = createApplication({ readAccepted: async () => null });
  const response = await app(new Request(env.APP_ORIGIN + '/auth/callback?code=forged&state=forged'), env);
  expect(response.status).toBe(401);
  expect(response.headers.get('set-cookie')).toContain('Max-Age=0');
});


test('verified Google owner signs in and receives a revocable month-long session for private reads', async () => {
  const { response, session } = await login();
  expect(response.status).toBe(303);
  expect(response.headers.get('location')).toBe('/');
  expect(response.headers.getSetCookie().join(';')).toContain('Max-Age=2592000');
  expect(response.headers.getSetCookie().join(';')).toContain('HttpOnly; Secure; SameSite=Lax');
  expect(session).not.toContain('discarded-access-token');
  const read = await application()(new Request(env.APP_ORIGIN + '/api/snapshot', { headers: { Cookie: session! } }), env);
  expect(await read.json()).toEqual({ state: 'empty' });
});

test('invalid Google proofs and login transactions never create a private session', async () => {
  for (const options of [
    { claims: { email: 'other@example.test' } }, { claims: { email_verified: false } },
    { claims: { nonce: 'wrong' } }, { audience: 'attacker' }, { issuer: 'https://attacker.test' },
    { expired: true }, { forged: true }, { state: 'wrong' }, { noCookie: true }, { failExchange: true },
  ]) {
    const { response, session } = await login(options);
    expect(response.status).toBe(401);
    expect(session).toBeUndefined();
    expect(response.headers.get('cache-control')).toBe('private, no-store');
  }
});

test('first verified email binds a subject permanently and rejects later different subjects', async () => {
  const db: DatabaseState = { sessions: new Map() };
  expect((await login({}, db)).response.status).toBe(303);
  const replacement = await login({ claims: { sub: 'different-google-sub' } }, db);
  expect(replacement.response.status).toBe(401);
  expect(replacement.session).toBeUndefined();
});

test('logout requires a same-origin POST and invalidates even a copied old cookie', async () => {
  const { app, session } = await login();
  const headers = { Cookie: session! };
  expect((await app(new Request(env.APP_ORIGIN + '/auth/logout', { method: 'POST', headers }), env)).status).toBe(403);
  const response = await app(new Request(env.APP_ORIGIN + '/auth/logout', { method: 'POST', headers: { ...headers, Origin: env.APP_ORIGIN } }), env);
  expect(response.status).toBe(303);
  expect(response.headers.get('set-cookie')).toContain('Max-Age=0');
  expect((await app(new Request(env.APP_ORIGIN + '/api/snapshot', { headers }), env)).status).toBe(401);
});

test('private page offers the same-origin logout form', async () => {
  const { readFile } = await import('node:fs/promises');
  const { session } = await login();
  const app = createApplication({ readAccepted: async () => null, authQuery: databaseTransport() });
  const response = await app(new Request(env.APP_ORIGIN + '/', { headers: { Cookie: session! } }),
    { ...env, ASSETS: { fetch: async () => new Response(await readFile('hosted/public/index.html', 'utf8')) } });
  expect(await response.text()).toContain('action="/auth/logout" method="post"');
});

test('alternate hostnames cannot dispatch the configured application', async () => {
  const { session } = await login();
  const response = await application()(new Request('https://alternate.example.test/api/snapshot', { headers: { Cookie: session! } }), env);
  expect(response.status).toBe(403);
});


test('sessions expire absolutely after thirty days and cookie tampering never authorizes', async () => {
  const { app, session } = await login();
  const request = (value: string) => new Request(env.APP_ORIGIN + '/api/snapshot', { headers: { Cookie: value } });
  expect((await app(request(session! + 'tampered'), env)).status).toBe(401);
  vi.useFakeTimers();
  try {
    vi.setSystemTime(Date.now() + 30 * 24 * 60 * 60 * 1000 + 1000);
    expect((await app(request(session!), env)).status).toBe(401);
  } finally { vi.useRealTimers(); }
});

test('tampered login transaction and unavailable session storage fail closed', async () => {
  const { app, callback, flowCookie, session } = await login();
  const forgedFlow = new Request(callback, { headers: { Cookie: flowCookie + 'tampered' } });
  expect((await app(forgedFlow, env)).status).toBe(401);
  const unavailable = createApplication({ readAccepted: async () => { throw Error('must not reach data'); },
    authQuery: async () => { throw Error('private connection details'); } });
  const response = await unavailable(new Request(env.APP_ORIGIN + '/api/snapshot', { headers: { Cookie: session! } }), env);
  expect(response.status).toBe(503);
  expect(await response.json()).toEqual({ state: 'error', error: 'authentication_unavailable' });
});
