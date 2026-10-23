import type { TargetsStore } from './targets';
import { beginLogin, finishLogin, cookie, readCookie, flowCookie, sessionCookie, month, type GoogleFetch } from './auth';
import { AuthStore, authQuery, type AuthQuery } from './auth-store';
import { generateRandomState } from 'oauth4webapi';
import { loginPage } from './login-page';

export interface Environment {
  IMPORTS_ENABLED?: string;
  GOOGLE_CLIENT_ID: string;
  GOOGLE_CLIENT_SECRET: string;
  SESSION_SECRET: string;
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
  cryptoPlans?(method: string, value: unknown, env: Environment): Promise<Record<string, unknown>>;
  cryptoLevels?(value: unknown, env: Environment): Promise<Record<string, unknown>>;
  contribution?(value: unknown, env: Environment): Promise<Record<string, unknown>>;
  refresh?(env: Environment): Promise<Record<string, unknown>>;
  targets?(env: Environment): TargetsStore;
  handleImports?(request: Request, env: Environment): Promise<Response>;
  readAccepted(env: Environment): Promise<AcceptedSnapshot | null>;
  // External provider HTTP and database transports; no identity bypass.
  googleFetch?: GoogleFetch;
  authQuery?: AuthQuery;
}
function privateResponse(body: BodyInit | null, status: number, headers?: HeadersInit) {
  const result = new Headers(headers);
  result.set('Cache-Control', 'private, no-store');
  result.set('X-Content-Type-Options', 'nosniff');
  result.set('Referrer-Policy', 'no-referrer');
  result.set('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; form-action 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  result.set('Vary', 'Cookie');
  return new Response(body, { status, headers: result });
}
function signInResponse(failed: boolean) {
  const { html, nonce } = loginPage(failed);
  const response = privateResponse(html, failed ? 401 : 200, { 'Content-Type': 'text/html; charset=utf-8' });
  response.headers.set('Content-Security-Policy', `default-src 'none'; style-src 'nonce-${nonce}'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`);
  if (failed) response.headers.set('Set-Cookie', cookie(flowCookie, '', 0));
  return response;
}
function json(body: unknown, status = 200) {
  return privateResponse(JSON.stringify(body), status, { 'Content-Type': 'application/json' });
}
function configured(env: Environment) {
  return !!env.GOOGLE_CLIENT_ID && !!env.GOOGLE_CLIENT_SECRET && (env.SESSION_SECRET || '').length >= 32
    && /^[^\s@]+@[^\s@]+$/.test(env.OWNER_EMAIL || '')
    && !!env.DATABASE_URL && /^https:\/\/[^/]+$/.test(env.APP_ORIGIN || '');
}
export function createApplication(dependencies: Dependencies) {
  const handle = async (request: Request, env: Environment): Promise<Response> => {
    if (!configured(env)) return json({ state: 'error', error: 'service_unconfigured' }, 503);
    const url = new URL(request.url);
    if (url.origin !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
    const path = url.pathname;
    if (request.method === 'GET' && path === '/login') return signInResponse(false);
    if (request.method === 'GET' && path === '/auth/login') {
      const response = await beginLogin(env);
      return privateResponse(null, response.status, response.headers);
    }
    const store = new AuthStore(dependencies.authQuery || authQuery(env.DATABASE_URL));
    if (request.method === 'GET' && path === '/auth/callback') {
      try {
        const identity = await finishLogin(request, env, dependencies.googleFetch);
        if (!await store.bindOwner(identity.sub, identity.email)) throw Error('owner mismatch');
        const token = generateRandomState();
        await store.createSession(token, identity.sub, identity.email);
        const response = privateResponse(null, 303, { Location: '/' });
        response.headers.append('Set-Cookie', cookie(flowCookie, '', 0));
        response.headers.append('Set-Cookie', cookie(sessionCookie, token, month));
        return response;
      } catch {
        return signInResponse(true);
      }
    }
    const token = readCookie(request, sessionCookie);
    let authorized = false;
    try { authorized = !!token && await store.ownerSession(token, env.OWNER_EMAIL.toLowerCase()); }
    catch { return json({ state: 'error', error: 'authentication_unavailable' }, 503); }
    if (!authorized) {
      if (path === '/' && request.method === 'GET') return privateResponse(null, 303, { Location: '/login' });
      return json({ error: 'authentication_required' }, 401);
    }
    if (path === '/auth/logout' && request.method === 'POST') {
      if (request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      try { await store.revokeSession(token!); }
      catch { return json({ state: 'error', error: 'authentication_unavailable' }, 503); }
      return privateResponse(null, 303, { Location: '/login', 'Set-Cookie': cookie(sessionCookie, '', 0) });
    }
    if (path === '/api/crypto/levels') {
      if (request.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);
      if (request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      try {
        if (!dependencies.cryptoLevels) throw Error('unavailable');
        let value: unknown;
        try { const body = await request.text(); if (body.length > 5000) throw Error(); value = JSON.parse(body); }
        catch { return json({ error: 'invalid_request' }, 400); }
        const result = await dependencies.cryptoLevels(value, env);
        return json(result, result.state === 'stale' ? 409 : 200);
      } catch (error) {
        return error instanceof Error && ['invalid_request','invalid_coin','invalid_percentiles'].includes(error.message)
          ? json({ error: error.message }, 400) : json({ error: 'crypto_levels_unavailable' }, 503);
      }
    }
    if (path === '/api/crypto/plans' || path === '/api/crypto/plans/preview') {
      if (path.endsWith('/preview') && request.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);
      if (!['GET','POST'].includes(request.method)) return json({ error: 'method_not_allowed' }, 405);
      if (request.method === 'POST' && request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      try {
        if (!dependencies.cryptoPlans) throw Error('unavailable');
        let value: unknown = new URL(request.url).searchParams.get('coin');
        if (request.method === 'POST') {
          try { const body = await request.text(); if (body.length > 10000) throw Error(); value = JSON.parse(body); }
          catch { return json({ error: 'invalid_crypto_plan' }, 400); }
        }
        const result = await dependencies.cryptoPlans(path.endsWith('/preview') ? 'PREVIEW' : request.method, value, env);
        return json(result, ['conflict','replacement_required'].includes(String(result.state)) ? 409 : result.state === 'unavailable' ? 503 : 200);
      } catch (error) {
        const known = ['invalid_crypto_plan','invalid_percentiles','reviewed_sale_quantity_terms_required','verified_crypto_holding_required','positive_tactical_quantity_required','stage_below_reviewed_minimum'];
        return error instanceof Error && known.includes(error.message) ? json({ error: error.message }, 400) : json({ error: 'crypto_plan_unavailable' }, 503);
      }
    }
    if (path === '/api/contribution') {
      if (request.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);
      if (request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      try {
        if (!dependencies.contribution) throw Error('unavailable');
        let value: unknown;
        try { const body = await request.text(); if (body.length > 5000) throw Error(); value = JSON.parse(body); }
        catch { return json({ error: 'invalid_request' }, 400); }
        const result = await dependencies.contribution(value, env);
        return json(result, result.state === 'stale' ? 409 : 200);
      } catch (error) {
        return error instanceof Error && ['invalid_request','invalid_budget','invalid_choice'].includes(error.message)
          ? json({ error: error.message }, 400) : json({ error: 'contribution_unavailable' }, 503);
      }
    }
    if (path === '/api/refresh') {
      if (request.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);
      if (request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      try {
        if (!dependencies.refresh) throw Error('unavailable');
        return json(await dependencies.refresh(env));
      } catch { return json({ state: 'retained', reason: 'refresh_unavailable' }, 503); }
    }
    if (path === '/api/targets') {
      if (!['GET', 'PUT'].includes(request.method)) return json({ error: 'method_not_allowed' }, 405);
      if (request.method === 'PUT' && request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      try {
        const targets = dependencies.targets?.(env);
        if (!targets) throw Error('unavailable');
        if (request.method === 'GET') return json(await targets.read());
        if (Number(request.headers.get('Content-Length')) > 30000) return json({ error: 'invalid_targets' }, 400);
        let input: unknown;
        try { const body = await request.text(); if (body.length > 30000) throw Error(); input = JSON.parse(body); }
        catch { return json({ error: 'invalid_targets' }, 400); }
        const result = await targets.save(input);
        return json(result, result.state === 'conflict' ? 409 : 200);
      } catch (error) {
        return error instanceof Error && error.message === 'invalid_targets' ? json({ error: 'invalid_targets' }, 400)
          : json({ error: 'targets_unavailable' }, 503);
      }
    }
    if (path === '/api/imports' || /^\/api\/imports\/[^/]+\/retry$/.test(path)) {
      if (!dependencies.handleImports) return json({ error: 'imports_unavailable' }, 503);
      const response = await dependencies.handleImports(request, env);
      return privateResponse(response.body, response.status, response.headers);
    }
    // Authorization precedes method/path dispatch, including matching assets and unknown routes.
    if (!['GET', 'HEAD'].includes(request.method)) {
      if (request.headers.get('Origin') !== env.APP_ORIGIN) return json({ error: 'origin_rejected' }, 403);
      return json({ error: 'method_not_allowed' }, 405);
    }
    if (url.pathname.startsWith('/auth/')) return json({ error: 'not_found' }, 404);
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
      return response;
    } catch { return json({ state: 'error', error: 'asset_unavailable' }, 503); }
  };
  return async (request: Request, env: Environment): Promise<Response> => {
    const response = await handle(request, env);
    return request.method === 'HEAD' ? new Response(null, { status: response.status, headers: response.headers }) : response;
  };
}
