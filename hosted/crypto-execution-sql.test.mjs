import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '@electric-sql/pglite';
const schema = name => readFile(new URL(`./${name}.sql`,import.meta.url),'utf8');
export const actual = {schema_version:'canonical-disposal-v1',execution_id:'actual-fill-1',identity_version:'execution-v3',identity_fingerprint:'synthetic-fingerprint',identity_occurrence:'1',
  broker_asset_id:'synthetic-btc',symbol:'BTC-EUR',asset_kind:'Cryptocurrency',order_id:'order-context-only',executed_at:'2026-01-05T09:00:00Z',quantity:'0.6',
  gross_proceeds_eur:'120',fees_eur:'3',disposed_cost_eur:'90',realized_gain_eur:'27',coverage:'verified_complete',allocation_policy:'canonical40-breakpoints-exact-rational-v1',
  cost_breakpoints:[{quantity:'0',cost_eur:'0'},{quantity:'0.3',cost_eur:'30'},{quantity:'0.6',cost_eur:'90'}],ledger_version:'import-ledger',financial_settings_version:'financial',ledger_cutoff:'2026-01-06T00:00:00Z'};

test('durable reports stay pending, explicit partial matching is idempotent and protects execution capacity',async()=>{
  const db=new PGlite();
  try {
    for(const name of ['schema','targets-schema','contribution-schema','crypto-market-schema','crypto-plan-schema','crypto-execution-schema'])await db.exec(await schema(name));
    const query=async(sql,params=[])=>(await db.query(sql,params)).rows;
    const plan={plan_id:'plan-test',state:'accepted',coin:'BTC-EUR',symbol:'BTC-EUR',asset_id:'synthetic-btc',accepted_at:'2026-01-01T00:00:00Z',ledger_version:'original',core_quantity:'0.2',held_quantity_at_acceptance:'1.2',
      stages:[{stage_id:'stage-1',quantity:'0.4'},{stage_id:'stage-2',quantity:'0.4'},{stage_id:'stage-3',quantity:'0.2'}]};
    const model={calculation_version:'decimal-accounting-v1',ledger_version:'import-ledger',settings_version:'financial',ledger:{schema_version:'ledger-v1',positions:[{broker_asset_id:'synthetic-btc',symbol:'BTC-EUR',asset_kind:'Cryptocurrency',quantity:'0.6'}],disposals:[actual]}};
    await query("INSERT INTO hosted_snapshot_generations VALUES('g1',now(),'synthetic',$1::jsonb)",[JSON.stringify(model)]);
    await query("INSERT INTO hosted_crypto_plan_history VALUES('plan-test','BTC-EUR','2026-01-01',$1::jsonb)",[JSON.stringify(plan)]);
    await db.exec("INSERT INTO hosted_snapshot_pointer VALUES(true,'g1'); UPDATE hosted_crypto_plan_state SET current_plan_id='plan-test',version=1 WHERE coin='BTC-EUR'");
    const read=async(coin='BTC-EUR')=>(await query('SELECT hosted_read_crypto_executions($1) AS result',[coin]))[0].result;
    const operate=async(request)=>(await query('SELECT hosted_record_crypto_execution($1::jsonb) AS result',[JSON.stringify(request)]))[0].result;
    const request={action:'report',coin:'BTC-EUR',operation_id:'report-operation',expected_version:'0',generation_id:'g1',plan_id:'plan-test',stage_id:'stage-1',quantity:'0.4'};
    const reported=await operate(request);
    assert.equal(reported.state,'reported'); assert.deepEqual(await operate(request),reported);
    const pending=await read(); assert.equal(pending.progress.pending_quantity,'0.4'); assert.equal(pending.progress.matched_quantity,'0');
    assert.equal((await operate({...request,quantity:'0.3'})).reason,'operation_id_reused');
    const match={...request,action:'match',operation_id:'matching-operation',expected_version:'1',report_id:reported.report_id,execution_id:actual.execution_id,quantity:'0.2'};
    const matched=await operate(match); assert.equal(matched.state,'matched'); assert.deepEqual(await operate(match),matched);
    const partial=await read(); assert.equal(partial.reports[0].pending_quantity,'0.2'); assert.equal(partial.progress.matched_quantity,'0.2');
    assert.equal(partial.allocations[0].receipt.display.realized_gain_eur,'19.00');
    assert.equal((await operate({...match,operation_id:'stale-operation'})).reason,'snapshot_or_plan_changed');
    assert.equal((await operate({...match,operation_id:'overfill-operation',expected_version:'2',quantity:'0.3'})).reason,'report_quantity_exceeded');
    assert.equal((await operate({...match,operation_id:'complete-operation',expected_version:'2'})).state,'matched');
    const second={...match,operation_id:'second-stage-match',expected_version:'3',stage_id:'stage-2',quantity:'0.2'}; delete second.report_id;
    assert.equal((await operate(second)).state,'matched');
    const complete=await read(); assert.equal(complete.progress.matched_quantity,'0.6'); assert.equal(complete.executions[0].available_quantity,'0');
    assert.equal(complete.progress.reconciled_ledger_version,'import-ledger');
    assert.equal((await operate({...second,operation_id:'duplicate-execution',expected_version:'4',quantity:'0.1'})).reason,'execution_capacity_exhausted');
    assert.equal((await read('ETH-EUR')).progress.matched_quantity,'0');
    const republish=async(id,change)=>{
      const next=structuredClone(model);change(next);
      await query('INSERT INTO hosted_snapshot_generations VALUES($1,now(),\'synthetic\',$2::jsonb)',[id,JSON.stringify(next)]);
      await query('UPDATE hosted_snapshot_pointer SET generation_id=$1',[id]);
    };
    await republish('corrected',next=>{next.ledger.disposals[0].fees_eur='4';next.ledger.disposals[0].realized_gain_eur='26';});
    const corrected=await read(); assert.equal(corrected.progress.reconciliation_required,true); assert.equal(corrected.progress.matched_quantity,'0.6');
    assert.equal(corrected.progress.reconciled_ledger_version,null);
    assert.equal(corrected.allocations[0].receipt.display.realized_gain_eur,'19.00');
    assert.equal((await operate({...second,operation_id:'corrected-match',expected_version:'4',generation_id:'corrected',quantity:'0.1'})).reason,'execution_facts_changed_review');
    await republish('reversed',next=>{next.ledger.disposals=[];next.ledger.positions[0].quantity='1.2';});
    const reversed=await read();assert.equal(reversed.progress.reconciliation_required,true);assert.equal(reversed.progress.matched_quantity,'0.6');
    assert.equal(reversed.allocations.length,3);
    await republish('manual-sale',next=>{next.ledger.positions[0].quantity='0.5';next.ledger.disposals.push({...actual,execution_id:'manual-sale',quantity:'0.1'});});
    assert.equal((await read()).progress.reconciled_ledger_version,null);
    // Persisted capacity is global across plan versions and cannot be replayed.
    await db.exec("UPDATE hosted_snapshot_pointer SET generation_id='g1'");
    await db.exec(`CREATE ROLE execution_worker;
      GRANT EXECUTE ON FUNCTION hosted_read_crypto_executions(text),hosted_record_crypto_execution(jsonb) TO execution_worker;
      SET ROLE execution_worker`);
    assert.equal((await read()).progress.matched_quantity,'0.6');
    await assert.rejects(db.exec('DELETE FROM hosted_crypto_match_allocations'),/permission denied/);
    await db.exec('RESET ROLE');
    const permissions=await query("SELECT has_function_privilege('public',oid,'EXECUTE') AS allowed FROM pg_proc WHERE proname IN ('hosted_read_crypto_executions','hosted_record_crypto_execution')");
    assert.equal(permissions.length,2);assert.ok(permissions.every(row=>!row.allowed));
  }finally{await db.close();}
});
test('actual split execution receipts retain nonlinear canonical cost and exact rational totals',async()=>{
  const db = new PGlite();
  try {
    for(const name of ['schema','targets-schema','contribution-schema','crypto-market-schema','crypto-plan-schema','crypto-execution-schema'])await db.exec(await schema(name));
    const receipt=async(a,b)=>(await db.query('SELECT hosted_actual_execution_receipt($1::jsonb,$2::numeric,$3::numeric) AS receipt',[JSON.stringify(actual),a,b])).rows[0].receipt;
    const first=await receipt('0','0.4'),second=await receipt('0.4','0.6');
    assert.deepEqual(first.disposed_cost,{numerator:'50',denominator:'1'});
    assert.deepEqual(second.disposed_cost,{numerator:'40',denominator:'1'});
    assert.equal(first.display.realized_gain_eur,'28.00');
    assert.equal(second.display.realized_gain_eur,'-1.00');
    const third=await receipt('0','0.1');
    assert.deepEqual(third.fees,{numerator:'1',denominator:'2'});
    await assert.rejects(receipt('0.5','0.7'),/range/);
  }finally{await db.close();}
});
