import * as oauth from 'oauth4webapi';
import { SignJWT, jwtVerify } from 'jose';
import type { Environment } from './application';

export const google = {
  issuer: 'https://accounts.google.com', authorization_endpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
  token_endpoint: 'https://oauth2.googleapis.com/token', jwks_uri: 'https://www.googleapis.com/oauth2/v3/certs',
};
export const flowCookie = '__Host-degiro-flow';
export const sessionCookie = '__Host-degiro-session';
export const month = 30 * 24 * 60 * 60;
export function cookie(name: string, value: string, age: number) {
  return `${name}=${value}; Path=/; Max-Age=${age}; HttpOnly; Secure; SameSite=Lax`;
}
export function readCookie(request: Request, name: string) {
  const values = (request.headers.get('Cookie') || '').split(';').map(value => value.trim()).filter(value => value.startsWith(name + '='));
  return values.length === 1 ? values[0].slice(name.length + 1) : undefined;
}
const secret = (env: Environment) => new TextEncoder().encode(env.SESSION_SECRET);
export async function beginLogin(env: Environment) {
  const state = oauth.generateRandomState(), nonce = oauth.generateRandomNonce(), verifier = oauth.generateRandomCodeVerifier();
  const flow = await new SignJWT({ state, nonce, verifier }).setProtectedHeader({ alg: 'HS256', typ: 'JWT' })
    .setIssuer(env.APP_ORIGIN).setAudience('google-login').setIssuedAt().setExpirationTime('10m').sign(secret(env));
  const url = new URL(google.authorization_endpoint);
  url.search = new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, redirect_uri: env.APP_ORIGIN + '/auth/callback',
    response_type: 'code', scope: 'openid email', state, nonce, code_challenge_method: 'S256',
    code_challenge: await oauth.calculatePKCECodeChallenge(verifier) }).toString();
  return new Response(null, { status: 302, headers: { Location: url.href, 'Set-Cookie': cookie(flowCookie, flow, 600) } });
}
export async function readFlow(request: Request, env: Environment) {
  const token = readCookie(request, flowCookie);
  if (!token) throw Error('missing flow');
  const { payload } = await jwtVerify(token, secret(env), { algorithms: ['HS256'], issuer: env.APP_ORIGIN,
    audience: 'google-login', requiredClaims: ['iat', 'exp', 'state', 'nonce', 'verifier'], maxTokenAge: '10m' });
  if (typeof payload.state !== 'string' || typeof payload.nonce !== 'string' || typeof payload.verifier !== 'string') throw Error('invalid flow');
  return { state: payload.state, nonce: payload.nonce, verifier: payload.verifier };
}
export type GoogleFetch = typeof fetch;
export async function finishLogin(request: Request, env: Environment, transport?: GoogleFetch) {
  const flow = await readFlow(request, env);
  const client = { client_id: env.GOOGLE_CLIENT_ID, id_token_signed_response_alg: 'RS256' };
  const parameters = oauth.validateAuthResponse(google, client, new URL(request.url), flow.state);
  const options = { [oauth.customFetch]: transport, signal: AbortSignal.timeout(5000) };
  const response = await oauth.authorizationCodeGrantRequest(google, client, oauth.ClientSecretPost(env.GOOGLE_CLIENT_SECRET),
    parameters, env.APP_ORIGIN + '/auth/callback', flow.verifier, options);
  const tokens = await oauth.processAuthorizationCodeResponse(google, client, response, { expectedNonce: flow.nonce, requireIdToken: true });
  await oauth.validateApplicationLevelSignature(google, response, options);
  const claims = oauth.getValidatedIdTokenClaims(tokens)!;
  if (claims.email_verified !== true || typeof claims.email !== 'string' || claims.email.toLowerCase() !== env.OWNER_EMAIL.toLowerCase()
      || typeof claims.sub !== 'string' || !claims.sub) throw Error('owner required');
  // Neither access nor refresh tokens are persisted or sent to the browser.
  return { sub: claims.sub, email: claims.email.toLowerCase() };
}
