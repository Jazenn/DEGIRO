import { expect, test } from 'vitest';
import { cryptoPlans, type PlanStore } from './crypto-plan-store';
import { prepareCryptoPlan } from './crypto-plan';
import { now, snapshot, terms, request } from './crypto-plan-test-support';
import {cryptoExecutions} from './crypto-execution-store';

test('replacement requires the reviewed prior identity and preserves it on the new plan', async () => {
  const old = prepareCryptoPlan(snapshot, terms, request, now, {});
  const store: PlanStore = {
    read: async () => ({version:'1',plan:old}), prior:async()=>null,
    context:async()=>({snapshot,terms,market:{state:'ready',market_version:'market1',context:[]}}),
    commit:async (_request,plan)=>({state:'accepted',plan}),
    replacement:async()=>({state:'ready'}),
  };
  const run=cryptoPlans(store,()=>now);
  const replacement={...request,expected_version:'1',operation_id:'replace-operation',replace_plan_id:old.plan_id,
    expected_execution_version:'2',replacement_reason:'Reviewed partial sale and corrected records'};
  expect((await run('PREVIEW',replacement)).state).toBe('preview');
  expect((await run('POST',replacement)).plan).toMatchObject({replaces_plan_id:old.plan_id,replacement_reason:replacement.replacement_reason});
  expect((await run('POST',{...replacement,replace_plan_id:'plan-wrong-plan'})).state).toBe('conflict');
  expect((await run('POST',{...request,expected_version:'1'})).state).toBe('replacement_required');
});

test('cancellation validates a reason without requiring a new stage quantity',async()=>{
  const commands:unknown[]=[];
  const run=cryptoExecutions({read:async()=>({}),commit:async value=>{commands.push(value);return {state:'cancelled'};}});
  const cancel={coin:'BTC-EUR',action:'cancel',operation_id:'cancel-operation',expected_version:'1',generation_id:'g1',plan_id:'p1',report_id:'r1',note:'Reviewed duplicate remainder'};
  expect((await run('POST',cancel)).state).toBe('cancelled');
  await expect(run('POST',{...cancel,note:'short'})).rejects.toThrow('invalid_crypto_execution');
  expect(commands).toHaveLength(1);
});
