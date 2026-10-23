import { generateKeyPair, exportJWK, SignJWT } from 'jose';
import { createApplication, type Environment } from './application';
import type { AuthQuery } from './auth-store';
import { calculatePKCECodeChallenge } from 'oauth4webapi';

export const env: Environment = {
  GOOGLE_CLIENT_ID: 'client', GOOGLE_CLIENT_SECRET: 'synthetic-secret', SESSION_SECRET: 'a'.repeat(64),
  OWNER_EMAIL: 'owner@example.test', DATABASE_URL: 'postgres://synthetic', APP_ORIGIN: 'https://portfolio.example.test',
  ASSETS: { fetch: async () => new Response('<h1>Private Snapshot</h1>') },
};
const key = await generateKeyPair('RS256', { extractable: true });
const jwk = { ...await exportJWK(key.publicKey), kid: 'synthetic', alg: 'RS256' };
export interface DatabaseState {
  owner?: { sub: unknown; email: unknown };
  sessions: Map<unknown, { sub: unknown; email: unknown; expires: number }>;
}
export const database: DatabaseState = { sessions: new Map() };
export function databaseTransport(db = database): AuthQuery {
  return async (sql, params) => {
    if (sql.startsWith('INSERT INTO hosted_owner_identity')) { db.owner ||= { sub: params[0], email: params[1] }; return []; }
    if (sql.startsWith('SELECT google_sub, owner_email')) return db.owner ? [{ google_sub: db.owner.sub, owner_email: db.owner.email }] : [];
    if (sql.startsWith('INSERT INTO hosted_sessions')) { db.sessions.set(params[0], { sub: params[1], email: params[2], expires: Date.now() + 2592000000 }); return []; }
    if (sql.startsWith('SELECT s.google_sub')) {
      const session = db.sessions.get(params[0]);
      return session && session.expires > Date.now() && session.email === params[1] && session.sub === db.owner?.sub && session.email === db.owner?.email ? [{ google_sub: session.sub }] : [];
    }
    if (sql.startsWith('DELETE FROM hosted_sessions')) { db.sessions.delete(params[0]); return []; }
    throw Error('Unexpected database operation');
  };
}
export interface IdentityOptions {
  claims?: Record<string, unknown>; audience?: string; issuer?: string; expired?: boolean; forged?: boolean;
  state?: string; noCookie?: boolean; failExchange?: boolean;
}
export function application(read: (env: Environment) => Promise<any> = async () => null) {
  return createApplication({ readAccepted: read, authQuery: databaseTransport() });
}
export async function login(options: IdentityOptions = {}, db = database) {
  let nonce = '', challenge = '';
  const provider: typeof fetch = async (input, init) => {
    if (String(input) === 'https://www.googleapis.com/oauth2/v3/certs') return Response.json({ keys: [jwk] });
    if (String(input) !== 'https://oauth2.googleapis.com/token') throw Error('Unexpected provider URL');
    const body = new URLSearchParams(init?.body as string);
    if (body.get('client_secret') !== 'synthetic-secret' || body.get('code') !== 'synthetic-code'
      || await calculatePKCECodeChallenge(body.get('code_verifier')!) !== challenge) throw Error('Invalid exchange');
    if (options.failExchange) return Response.json({ error: 'invalid_grant' }, { status: 400 });
    const signingKey = options.forged ? await generateKeyPair('RS256') : key;
    const idToken = await new SignJWT({ sub: 'owner-google-sub', email: 'owner@example.test', email_verified: true, nonce, ...options.claims })
      .setProtectedHeader({ alg: 'RS256', kid: 'synthetic' }).setIssuer(options.issuer || 'https://accounts.google.com')
      .setAudience(options.audience || 'client').setIssuedAt().setExpirationTime(options.expired ? 1 : '1h').sign(signingKey.privateKey);
    return Response.json({ access_token: 'discarded-access-token', token_type: 'Bearer', id_token: idToken });
  };
  const app = createApplication({ readAccepted: async () => null, authQuery: databaseTransport(db), googleFetch: provider });
  const start = await app(new Request(env.APP_ORIGIN + '/auth/login'), env);
  const url = new URL(start.headers.get('location')!);
  nonce = url.searchParams.get('nonce')!; challenge = url.searchParams.get('code_challenge')!;
  const flowCookie = start.headers.get('set-cookie')!.split(';')[0];
  const callback = new Request(env.APP_ORIGIN + '/auth/callback?code=synthetic-code&state=' + (options.state || url.searchParams.get('state')),
    { headers: options.noCookie ? {} : { Cookie: flowCookie } });
  const response = await app(callback, env);
  const session = response.headers.getSetCookie().find(value => value.startsWith('__Host-degiro-session='))?.split(';')[0];
  return { app, response, session, flowCookie, callback };
}
