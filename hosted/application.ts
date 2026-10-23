import { createLocalJWKSet, createRemoteJWKSet, jwtVerify, type JSONWebKeySet } from 'jose';

export interface Environment {
  ACCESS_ISSUER: string;
  ACCESS_AUDIENCE: string;
  OWNER_EMAIL: string;
  DATABASE_URL: string;
  APP_ORIGIN: string;
  ASSETS: { fetch(request: Request): Promise<Response> };
}
export interface AcceptedSnapshot {
  generation_id: string;
  published_at: string;
  data_classification: 'synthetic' | 'private';
  read_model: Record<string, unknown>;
}
export interface SnapshotReader { readAccepted(): Promise<AcceptedSnapshot | null> }
interface Dependencies {
  readAccepted(env: Environment): Promise<AcceptedSnapshot | null>;
  // Test seam is the external identity provider's public key document, never a bypass token.
  jwks?: () => Promise<JSONWebKeySet>;
}
const verifiers = new Map<string, ReturnType<typeof createRemoteJWKSet>>();
function privateResponse(body: BodyInit | null, status: number, headers?: HeadersInit) {
  const result = new Headers(headers);
  result.set('Cache-Control', 'private, no-store');
  result.set('X-Content-Type-Options', 'nosniff');
  result.set('Referrer-Policy', 'no-referrer');
  result.set('Vary', 'Cookie, Cf-Access-Jwt-Assertion');
  return new Response(body, { status, headers: result });
}
function json(body: unknown, status = 200) {
  return privateResponse(JSON.stringify(body), status, { 'Content-Type': 'application/json' });
}
function configured(env: Environment) {
  return /^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/.test(env.ACCESS_ISSUER || '')
    && !!env.ACCESS_AUDIENCE && /^[^\s@]+@[^\s@]+$/.test(env.OWNER_EMAIL || '')
    && !!env.DATABASE_URL && /^https:\/\/[^/]+$/.test(env.APP_ORIGIN || '');
}
export function createApplication(dependencies: Dependencies) {
  const handle = async (request: Request, env: Environment): Promise<Response> => {
    if (!configured(env)) return json({ state: 'error', error: 'service_unconfigured' }, 503);
    const assertion = request.headers.get('Cf-Access-Jwt-Assertion');
    if (!assertion) return json({ error: 'authentication_required' }, 401);
    let email: unknown;
    try {
      let verifier;
      if (dependencies.jwks) verifier = createLocalJWKSet(await dependencies.jwks());
      else {
        verifier = verifiers.get(env.ACCESS_ISSUER);
        if (!verifier) {
          verifier = createRemoteJWKSet(new URL(`${env.ACCESS_ISSUER}/cdn-cgi/access/certs`), { timeoutDuration: 5000 });
          verifiers.set(env.ACCESS_ISSUER, verifier);
        }
      }
      const { payload } = await jwtVerify(assertion, verifier, {
        algorithms: ['RS256'], issuer: env.ACCESS_ISSUER, audience: env.ACCESS_AUDIENCE,
        requiredClaims: ['exp', 'iat', 'email'], maxTokenAge: '31d',
      });
      email = payload.email;
    } catch { return json({ error: 'invalid_identity' }, 401); }
    if (typeof email !== 'string' || email.toLowerCase() !== env.OWNER_EMAIL.toLowerCase()) {
      return json({ error: 'owner_required' }, 403);
    }
    // Authorization precedes method/path dispatch, including matching assets and unknown routes.
    if (!['GET', 'HEAD'].includes(request.method)) {
      if (request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      return json({ error: 'method_not_allowed' }, 405);
    }
    const url = new URL(request.url);
    if (url.pathname === '/api/snapshot') {
      try {
        const snapshot = await dependencies.readAccepted(env);
        return json(snapshot ? { state: 'ready', snapshot } : { state: 'empty' });
      } catch { return json({ state: 'error', error: 'snapshot_unavailable' }, 503); }
    }
    if (url.pathname.startsWith('/api/')) return json({ error: 'not_found' }, 404);
    try {
      const asset = await env.ASSETS.fetch(request);
      const response = privateResponse(request.method === 'HEAD' ? null : asset.body, asset.status, asset.headers);
      response.headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
      return response;
    } catch { return json({ state: 'error', error: 'asset_unavailable' }, 503); }
  };
  return async (request: Request, env: Environment): Promise<Response> => {
    const response = await handle(request, env);
    return request.method === 'HEAD' ? new Response(null, { status: response.status, headers: response.headers }) : response;
  };
}
