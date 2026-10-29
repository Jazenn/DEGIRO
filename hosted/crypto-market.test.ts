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

test('HTTP market preview uses trusted prepared prices and rejects absent expired or corrupt summaries', async () => {
  const now = '2026-10-23T12:00:00Z';
  const summary = { schema: 'prepared-crypto-market-v1', coin: 'BTC-EUR', version: 'v1',
    cutoff: '2026-10-23T00:00:00Z', prepared_at: now, required_days: '365', available_days: '365',
    provider: 'synthetic', currency: 'EUR', adjustment_basis: 'unadjusted',
    sorted_prices: Array.from({length:365},(_,n)=>String(n+1)),
    context_prices: Array.from({length:90},(_,n)=>String(n+276)), context_retrieved_at: Array(90).fill(now) };
  let prepared: unknown = summary;
  const app = createApplication({ authQuery: databaseTransport(), readAccepted: async () => null,
    cryptoLevels: value => previewCryptoLevels(value, { read: async () => ({coin:'BTC-EUR',version:'v1',prepared_summary:prepared,attempted_at:now,diagnostics:[]}) }, now) });
  const cookie = (await login()).session!;
  const request = async (extra={}) => (await app(new Request(env.APP_ORIGIN+'/api/crypto/levels', {method:'POST', headers:{Cookie:cookie,Origin:env.APP_ORIGIN},body:JSON.stringify({coin:'BTC-EUR',...extra})}),env)).json();
  const ready = await request();
  expect(ready.state).toBe('ready');
  expect(ready.purchase.map((row:any)=>row.price_eur)).toEqual(['128.4','73.8','37.4']);
  expect(ready.sale.map((row:any)=>row.price_eur)).toEqual(['274','328.6','346.8']);
  expect(ready.context).toHaveLength(90);
  expect(ready.context[89].day).toBe('2026-10-22');
  expect((await request({templates:{purchase:['30','20','10'],sale:['75','90','95']}})).purchase[0].price_eur).toBe('110.2');
  const precise = {...summary, sorted_prices:Array(365).fill('9007199254740993.000000000000001'),
    context_prices:Array(90).fill('9007199254740993.000000000000001')};
  precise.sorted_prices[0]='9007199254740993';
  prepared=precise;
  const exact=await request({templates:{purchase:['0','20','10'],sale:['75','90','100']}});
  expect(exact.purchase[0].price_eur).toBe('9007199254740993');
  expect(exact.sale[2].price_eur).toBe('9007199254740993.000000000000001');
  prepared={...precise,sorted_prices:[...precise.sorted_prices.slice(1),precise.sorted_prices[0]]};
  expect((await request()).state).toBe('paused'); // prices collide as binary Numbers
  for (const changes of [null, {...summary,coin:'ETH-EUR'}, {...summary,version:'old'}, {...summary,cutoff:'2026-10-22T00:00:00Z'}, {...summary,sorted_prices:['0',...summary.sorted_prices.slice(1)]}, {...summary,context_prices:Array(90).fill('9999')}, {...summary,context_retrieved_at:Array(90).fill('2026-10-23T12:00:01Z')}, {...summary,sorted_prices:[...summary.sorted_prices].reverse()}]) {
    prepared=changes;
    const result=await request({prepared_summary:{state:'ready'}}); // client cannot replace trusted data
    expect(result.state).toBe('paused');expect(result.purchase).toEqual([]);
  }
});

test('warm public series rechecks payload, clock, coin and version while keeping drafts and returned data independent', async () => {
  let clock='2026-10-23T12:00:00Z';
  const make=(coin:string,version:string,offset=0)=>({coin,version,attempted_at:clock,diagnostics:[],prepared_summary:{
    schema:'prepared-crypto-market-v1',coin,version,cutoff:'2026-10-23T00:00:00Z',prepared_at:clock,
    required_days:'365',available_days:'365',provider:'synthetic',currency:'EUR',adjustment_basis:'unadjusted',
    sorted_prices:Array.from({length:365},(_,n)=>String(n+1+offset)),context_prices:Array.from({length:90},(_,n)=>String(n+276+offset)),context_retrieved_at:Array(90).fill(clock)}});
  const sources={'BTC-EUR':make('BTC-EUR','cache-v1'),'ETH-EUR':make('ETH-EUR','cache-v1',1000)};
  const reader={read:async(coin:string)=>sources[coin as keyof typeof sources]};
  const app=createApplication({authQuery:databaseTransport(),readAccepted:async()=>null,
    cryptoLevels:value=>previewCryptoLevels(value,reader,clock)});
  const cookie=(await login()).session!;
  const call=async(coin='BTC-EUR',extra={})=>(await app(new Request(env.APP_ORIGIN+'/api/crypto/levels',{method:'POST',headers:{Cookie:cookie,Origin:env.APP_ORIGIN},body:JSON.stringify({coin,...extra})}),env)).json();
  const first=await previewCryptoLevels({coin:'BTC-EUR'},reader,clock);
  if (!('context' in first)) throw Error('expected prepared market preview');
  first.context[0].price_eur='poison';first.templates.purchase[0]='99';
  expect((await call()).context[0].price_eur).toBe('276');
  expect((await call()).purchase[0].price_eur).toBe('128.4');
  expect((await call('BTC-EUR',{templates:{purchase:['30','20','10'],sale:['75','90','95']}})).purchase[0].price_eur).toBe('110.2');
  expect((await call('ETH-EUR')).purchase[0].price_eur).toBe('1128.4');
  const summary=sources['BTC-EUR'].prepared_summary;
  summary.sorted_prices.reverse();expect((await call()).state).toBe('paused');
  summary.sorted_prices.reverse();expect((await call()).state).toBe('ready');
  clock='2026-10-23T11:59:59Z';expect((await call()).state).toBe('paused');
  clock='2026-10-24T00:00:00Z';expect((await call()).state).toBe('paused');
  clock='2026-10-23T12:00:00Z';expect((await call()).state).toBe('ready');
  summary.version='cache-v2';expect((await call()).state).toBe('paused');
  sources['BTC-EUR'].version='cache-v2';
  expect((await call('BTC-EUR',{market_version:'cache-v1'})).state).toBe('stale');
  expect((await call()).state).toBe('ready');
  summary.sorted_prices=summary.sorted_prices.map(price=>String(Number(price)*2));
  summary.context_prices=summary.context_prices.map(price=>String(Number(price)*2));
  summary.provider='updated synthetic source';
  const changed=await call();
  expect(changed.purchase[0].price_eur).toBe('256.8');
  expect(changed.context[0].provider).toBe('updated synthetic source');
  summary.context_retrieved_at[0]='2026-10-23T12:00:01Z';expect((await call()).state).toBe('paused');
});
