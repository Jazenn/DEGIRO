import { expect, test } from 'vitest';
import { createApplication } from './application';
import { cryptoPlans, NeonCryptoPlanStore } from './crypto-plan-store';
import { previewCryptoLevels } from './crypto-market-store';
import { databaseTransport, env, login } from './auth-test-support';
import { now, snapshot, terms, request } from './crypto-plan-test-support';

test('authenticated independent plans survive retries, stale edits, new purchases and missing history', async () => {
  const states = new Map(['BTC-EUR','ETH-EUR'].map(coin => [coin, { coin, version: '0', plan: null as any, history: [] as any[] }]));
  const operations = new Map<string, { request: unknown; result: any }>();
  let current: any = structuredClone(snapshot), available = true;
  current.read_model.ledger.positions.push({ ...current.read_model.ledger.positions[0], broker_asset_id: 'direct-eth', symbol: 'ETH-EUR' });
  const observations = Object.fromEntries(Array.from({length:365}, (_, index) => {
    const at = new Date(Date.parse('2026-10-23T00:00:00Z') - index * 86400000).toISOString();
    return [at, { price_eur: String(1000+index), observed_at: at, retrieved_at: now, provider: 'synthetic', currency: 'EUR', adjustment_basis: 'unadjusted' }];
  }));
  const store = new NeonCryptoPlanStore(async (sql, params) => {
    if (sql.startsWith('SELECT s.coin,s.asset_id')) {
      const coin = params[0]; return [{ ...terms, coin, ...(coin === 'ETH-EUR' ? { asset_id: 'direct-eth', symbol: 'ETH-EUR' } : {}) }];
    }
    if (sql.startsWith('SELECT s.coin,s.version')) return [states.get(String(params[0]))!];
    if (sql.startsWith('SELECT request=')) {
      const prior = operations.get(String(params[0]));
      return prior ? [{ same: JSON.stringify(prior.request) === params[1], result: prior.result }] : [];
    }
    const input = JSON.parse(String(params[0])), plan = JSON.parse(String(params[1]));
    const state = states.get(input.coin)!;
    const result = state.version !== input.expected_version || input.generation_id !== current.generation_id ? { state:'conflict' }
      : state.plan ? { state:'replacement_required' }
      : { state:'accepted', coin:input.coin, version:String(Number(state.version)+1), plan };
    if (result.state === 'accepted') Object.assign(state, { version: result.version, plan, history:[...state.history,plan] });
    operations.set(input.operation_id, { request: input, result }); return [{result}];
  }, async () => current, (coin,templates) => previewCryptoLevels({coin,templates}, {read:async () => ({coin,version:'market1',observations: available ? observations : {},attempted_at:now,diagnostics:[]})}, now));
  const app = createApplication({ authQuery:databaseTransport(), readAccepted:async()=>current,
    cryptoPlans:(method,value) => cryptoPlans(store,()=>now)(method,value) });
  const cookie = (await login()).session!;
  const call = (body: unknown, authorized=true, origin=env.APP_ORIGIN) => app(new Request(env.APP_ORIGIN+'/api/crypto/plans', {
    method:'POST',headers:{Cookie:authorized?cookie:'',Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(body)}),env);
  expect((await call(request,false)).status).toBe(401);
  expect((await call(request,true,'https://wrong.test')).status).toBe(403);
  expect((await call({...request,core_quantity:''})).status).toBe(400);
  const preview = await app(new Request(env.APP_ORIGIN+'/api/crypto/plans/preview', {method:'POST',headers:{Cookie:cookie,Origin:env.APP_ORIGIN},body:JSON.stringify(request)}),env);
  expect((await preview.json()).state).toBe('preview');
  expect(states.get('BTC-EUR')!.plan).toBeNull();
  const accepted = await (await call(request)).json();
  expect(accepted.state).toBe('accepted');
  expect(accepted.plan.stages.map((stage:any)=>stage.quantity)).toEqual(['0.4','0.2','0.1']);
  expect((await call({...request,operation_id:'device-b-edit'})).status).toBe(409);
  expect((await call({...request,core_quantity:'0.3'})).status).toBe(409);
  const eth = await (await call({...request,coin:'ETH-EUR',operation_id:'accept-eth-1',core_quantity:'0.4',templates:{purchase:['35','20','10'],sale:['80','90','95']}})).json();
  expect(eth.state).toBe('accepted');
  expect(eth.plan.source_market.templates.sale).toEqual(['80','90','95']);
  expect(eth.plan.source_market.suggested_sale_levels_eur[0]).toBe('1291.2');
  current = {...current,generation_id:'g2'};
  current.read_model.ledger.positions[0].quantity='2.01'; available=false;
  expect(await (await call(request)).json()).toEqual(accepted);
  const read = await app(new Request(env.APP_ORIGIN+'/api/crypto/plans?coin=BTC-EUR',{headers:{Cookie:cookie}}),env);
  const retained = await read.json();
  expect(retained.plan).toEqual(accepted.plan);
  expect(retained.history).toHaveLength(1);
  expect(retained.plan.stages[0].quantity).toBe('0.4');
  expect(states.get('ETH-EUR')!.plan.core_quantity).toBe('0.4');
});
