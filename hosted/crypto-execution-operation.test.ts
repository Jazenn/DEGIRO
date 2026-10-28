import { expect, test } from 'vitest';
import { createApplication } from './application';
import { cryptoExecutions } from './crypto-execution-store';
import { env, databaseTransport, login } from './auth-test-support';

test('execution operations require owner access and same-origin writes, validate quantities and retain conflict responses',async()=>{
  const operations:unknown[]=[];
  const store={read:async(coin:string)=>({state:'ready',coin,version:'1'}),commit:async(value:unknown)=>{operations.push(value);return {state:'conflict',reason:'execution_capacity_exhausted'};}};
  const app=createApplication({authQuery:databaseTransport(),readAccepted:async()=>null,cryptoExecutions:(method,value)=>cryptoExecutions(store)(method,value)});
  const body={coin:'BTC-EUR',action:'match',operation_id:'operation-match',expected_version:'1',generation_id:'g1',plan_id:'p1',stage_id:'s1',execution_id:'e1',quantity:'0.2'};
  const request=(cookie?:string,value:unknown=body,origin=env.APP_ORIGIN)=>new Request(env.APP_ORIGIN+'/api/crypto/executions',{method:'POST',headers:{Origin:origin,...(cookie?{Cookie:cookie}:{})},body:JSON.stringify(value)});
  expect((await app(request(),env)).status).toBe(401);
  const cookie=(await login()).session!;
  expect((await app(request(cookie,body,'https://other.example'),env)).status).toBe(403);
  expect((await app(request(cookie,{...body,quantity:'-0.2'}),env)).status).toBe(400);
  expect((await app(request(cookie,{...body,execution_id:null}),env)).status).toBe(400);
  const response=await app(request(cookie),env);
  expect(response.status).toBe(409); expect(await response.json()).toEqual({state:'conflict',reason:'execution_capacity_exhausted'});
  expect(response.headers.get('cache-control')).toBe('private, no-store'); expect(operations).toHaveLength(1);
  const read=await app(new Request(env.APP_ORIGIN+'/api/crypto/executions?coin=ETH-EUR',{headers:{Cookie:cookie}}),env);
  expect(await read.json()).toEqual({state:'ready',coin:'ETH-EUR',version:'1'});
});
