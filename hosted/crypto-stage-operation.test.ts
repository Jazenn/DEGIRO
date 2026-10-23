import { expect, test } from 'vitest';
import { createApplication } from './application';
import { previewStageReview } from './crypto-stage-store';
import { env, databaseTransport, login } from './auth-test-support';

test('stage review is private, same-origin and rejects stale generation without changing plans', async () => {
  const state = { version:'1', plan:null };
  const reader = { read: async () => ({ snapshot:{generation_id:'new',read_model:{}},state,fees:null }) };
  const app = createApplication({ authQuery:databaseTransport(),readAccepted:async()=>null,
    cryptoStageReview:value=>previewStageReview(value,reader,'2026-10-23T12:00:00Z') });
  const request = (cookie?:string,generation='new',origin=env.APP_ORIGIN) => new Request(env.APP_ORIGIN+'/api/crypto/stages/preview',{
    method:'POST',headers:{...(cookie?{Cookie:cookie}:{}),Origin:origin},body:JSON.stringify({coin:'BTC-EUR',generation_id:generation}) });
  expect((await app(request(),env)).status).toBe(401);
  const cookie=(await login()).session!;
  expect((await app(request(cookie,'old'),env)).status).toBe(409);
  expect((await app(request(cookie,'new','https://other.example'),env)).status).toBe(403);
  const response=await app(request(cookie),env);
  expect(response.headers.get('cache-control')).toBe('private, no-store');
  expect((await response.json()).reason).toBe('accepted_plan_required');
  expect(state.plan).toBeNull();
});
