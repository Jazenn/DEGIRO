import {PGlite} from '@electric-sql/pglite';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

test('replacement after a partial execution preserves consumed identities and cancelled report audit',async()=>{
  const db=new PGlite();
  try{
    for(const name of ['schema','targets-schema','contribution-schema','crypto-market-schema','crypto-plan-schema','crypto-execution-schema','crypto-replacement-schema'])
      await db.exec(await readFile(new URL(`./${name}.sql`,import.meta.url),'utf8'));
    const query=async(sql,params=[])=>(await db.query(sql,params)).rows;
    const command=async(name,value,plan)=>(await query(`SELECT ${name}($1::jsonb${plan?',$2::jsonb':''}) AS result`,[JSON.stringify(value),...(plan?[JSON.stringify(plan)]:[])]))[0].result;
    const model={calculation_version:'decimal-accounting-v1',ledger_version:'l1',settings_version:'s1',ledger:{schema_version:'ledger-v1',positions:[{broker_asset_id:'btc',symbol:'BTC-EUR',asset_kind:'Cryptocurrency',cost_coverage:'verified_complete',quantity:'1'}]}};
    await query("INSERT INTO hosted_snapshot_generations VALUES('g1',now(),'synthetic',$1::jsonb)",[JSON.stringify(model)]);
    await db.exec(`INSERT INTO hosted_snapshot_pointer VALUES(true,'g1');
      INSERT INTO hosted_execution_terms VALUES('btc','q1',0.01,0.01,0,0,0,0,'known','all_purchase_charges','EUR','SYNTHETIC','2000-01-01','2099-01-01');
      INSERT INTO hosted_crypto_sale_permissions VALUES('BTC-EUR','btc','BTC-EUR','sale1','q1',true,'SYNTHETIC','2000-01-01','2099-01-01');
      INSERT INTO hosted_crypto_market_history VALUES('BTC-EUR','m1','{}',now(),'[]')`);
    const request={coin:'BTC-EUR',operation_id:'first-operation',generation_id:'g1',expected_version:'0',core_quantity:'0.2',proportions:['50','30','20'],levels_eur:['100','200','300'],terms_revision:'sale1',market_version:'m1'};
    const planFor=(id,version)=>({plan_id:'plan-'+id,plan_version:version,coin:'BTC-EUR',asset_id:'btc',ledger_version:'l1',financial_settings_version:'s1',held_quantity_at_acceptance:'1',core_quantity:'0.2',original_tactical_quantity:'0.8',rounding_residual_quantity:'0',accepted_at:new Date().toISOString(),source_market:{valid_until:'2099-01-01T00:00:00Z'},stages:['0.4','0.24','0.16'].map((quantity,i)=>({stage_id:`plan-${id}:${i+1}`,state:'unfinished',quantity,proportion_pct:request.proportions[i],level_eur:request.levels_eur[i]}))});
    const old=planFor(request.operation_id,'1');
    assert.equal((await command('hosted_accept_crypto_plan',request,old)).state,'accepted');
    // Seed prior partial execution as the external persistence boundary fixture.
    await db.exec(`INSERT INTO hosted_crypto_reports VALUES('r1','BTC-EUR','${old.plan_id}','${old.plan_id}:1',0.4,'open','g1','l1','synthetic',now());
      INSERT INTO hosted_crypto_execution_capacity VALUES('fill1','btc',0.2,0.2,'{}');
      INSERT INTO hosted_crypto_match_allocations VALUES('a1','match-operation','BTC-EUR','${old.plan_id}','${old.plan_id}:1','r1','fill1',0,0.2,'{}','l1',now());
      UPDATE hosted_crypto_execution_state SET version=2 WHERE coin='BTC-EUR'`);
    const replacement={...request,operation_id:'replacement-operation',expected_version:'1',replace_plan_id:old.plan_id,expected_execution_version:'2',replacement_reason:'Reviewed partial sale and reconciled holdings'};
    let proposed={...planFor(replacement.operation_id,'2'),replaces_plan_id:old.plan_id,replacement_reason:replacement.replacement_reason,reviewed_execution_version:'2'};
    assert.equal((await command('hosted_accept_crypto_plan',replacement,proposed)).reason,'pending_reports_require_resolution');
    const cancel={coin:'BTC-EUR',action:'cancel',operation_id:'cancel-operation',expected_version:'2',generation_id:'g1',plan_id:old.plan_id,report_id:'r1',note:'Cancel unmatched duplicate remainder'};
    const cancelled=await command('hosted_cancel_crypto_report',cancel);
    assert.equal(cancelled.state,'cancelled');assert.equal(cancelled.version,'3');
    assert.deepEqual(await command('hosted_cancel_crypto_report',cancel),cancelled);
    // Canonical import publishes the reduced holding after the partial sale.
    const afterSale=structuredClone(model);afterSale.ledger_version='l2';afterSale.ledger.positions[0].quantity='0.8';
    await query("INSERT INTO hosted_snapshot_generations VALUES('g2',now(),'synthetic',$1::jsonb)",[JSON.stringify(afterSale)]);
    await db.exec("UPDATE hosted_snapshot_pointer SET generation_id='g2' WHERE singleton");
    const stale={...replacement,generation_id:'g2',operation_id:'stale-replacement'};
    assert.equal((await command('hosted_accept_crypto_plan',stale,proposed)).reason,'execution_state_changed');
    const ready={...replacement,generation_id:'g2',operation_id:'ready-replacement',expected_execution_version:'3'};
    proposed={...planFor(ready.operation_id,'2'),ledger_version:'l2',held_quantity_at_acceptance:'0.8',original_tactical_quantity:'0.6',
      stages:['0.3','0.18','0.12'].map((quantity,i)=>({...planFor(ready.operation_id,'2').stages[i],quantity})),
      replaces_plan_id:old.plan_id,replacement_reason:ready.replacement_reason,reviewed_execution_version:'3'};
    const accepted=await command('hosted_accept_crypto_plan',ready,proposed);
    assert.equal(accepted.state,'accepted');assert.deepEqual(await command('hosted_accept_crypto_plan',ready,proposed),accepted);
    assert.equal((await query("SELECT count(*)::text AS n FROM hosted_crypto_plan_history"))[0].n,'2');
    assert.equal((await query("SELECT allocated_quantity::text AS n FROM hosted_crypto_execution_capacity WHERE execution_id='fill1'"))[0].n,'0.2');
    assert.equal((await query("SELECT previous_report->>'status' AS status FROM hosted_crypto_report_events"))[0].status,'open');
    const events=(await query("SELECT hosted_read_crypto_report_events('BTC-EUR') AS events"))[0].events;
    assert.equal(events[0].reason,cancel.note);assert.equal(events[0].previous_report.quantity,0.4);
    assert.equal((await query("SELECT version::text FROM hosted_crypto_execution_state WHERE coin='ETH-EUR'"))[0].version,'0');
    assert.equal((await query("SELECT version::text FROM hosted_crypto_plan_state WHERE coin='ETH-EUR'"))[0].version,'0');
  }finally{await db.close();}
});

test('a correction or reversal of a matched earlier-plan execution suspends the replacement without changing its receipt',async()=>{
  const db=new PGlite();
  try{
    for(const name of ['schema','targets-schema','contribution-schema','crypto-market-schema','crypto-plan-schema','crypto-execution-schema','crypto-replacement-schema'])
      await db.exec(await readFile(new URL(`./${name}.sql`,import.meta.url),'utf8'));
    const query=async(sql,params=[])=>(await db.query(sql,params)).rows;
    const command=async(name,value,plan)=>(await query(`SELECT ${name}($1::jsonb${plan?',$2::jsonb':''}) AS result`,[JSON.stringify(value),...(plan?[JSON.stringify(plan)]:[])]))[0].result;
    const old={plan_id:'old-plan',state:'accepted',coin:'BTC-EUR',symbol:'BTC-EUR',asset_id:'btc',accepted_at:'2026-01-01T00:00:00Z',
      ledger_version:'l1',held_quantity_at_acceptance:'1',core_quantity:'0.2',stages:[{stage_id:'old-plan:1',quantity:'0.4'}]};
    const execution={schema_version:'canonical-disposal-v1',execution_id:'old-fill',broker_asset_id:'btc',symbol:'BTC-EUR',asset_kind:'Cryptocurrency',
      executed_at:'2026-01-05T09:00:00Z',quantity:'0.2',gross_proceeds_eur:'40',fees_eur:'1',disposed_cost_eur:'20',realized_gain_eur:'19',
      coverage:'verified_complete',allocation_policy:'canonical40-breakpoints-exact-rational-v1',cost_breakpoints:[{quantity:'0',cost_eur:'0'},{quantity:'0.2',cost_eur:'20'}]};
    const model={calculation_version:'decimal-accounting-v1',ledger_version:'l1',settings_version:'s1',ledger:{schema_version:'ledger-v1',
      positions:[{broker_asset_id:'btc',symbol:'BTC-EUR',asset_kind:'Cryptocurrency',cost_coverage:'verified_complete',quantity:'0.8'}],disposals:[execution]}};
    await query("INSERT INTO hosted_snapshot_generations VALUES('g1',now(),'synthetic',$1::jsonb)",[JSON.stringify(model)]);
    await query("INSERT INTO hosted_crypto_plan_history VALUES('old-plan','BTC-EUR','2026-01-01',$1::jsonb)",[JSON.stringify(old)]);
    await db.exec(`INSERT INTO hosted_snapshot_pointer VALUES(true,'g1');
      UPDATE hosted_crypto_plan_state SET current_plan_id='old-plan',version=1 WHERE coin='BTC-EUR';
      INSERT INTO hosted_execution_terms VALUES('btc','q1',0.01,0.01,0,0,0,0,'known','all_purchase_charges','EUR','SYNTHETIC','2000-01-01','2099-01-01');
      INSERT INTO hosted_crypto_sale_permissions VALUES('BTC-EUR','btc','BTC-EUR','sale1','q1',true,'SYNTHETIC','2000-01-01','2099-01-01');
      INSERT INTO hosted_crypto_market_history VALUES('BTC-EUR','m1','{}',now(),'[]')`);
    const matched=await command('hosted_record_crypto_execution',{action:'match',coin:'BTC-EUR',operation_id:'original-match',expected_version:'0',
      generation_id:'g1',plan_id:'old-plan',stage_id:'old-plan:1',quantity:'0.2',execution_id:'old-fill'});
    assert.equal(matched.state,'matched');
    const replacement={coin:'BTC-EUR',operation_id:'replacement-after-match',generation_id:'g1',expected_version:'1',replace_plan_id:'old-plan',
      expected_execution_version:'1',replacement_reason:'Reviewed actual sale and current remaining holdings',core_quantity:'0.2',
      proportions:['50','30','20'],levels_eur:['100','200','300'],terms_revision:'sale1',market_version:'m1'};
    const plan_id='plan-replacement-after-match';
    const proposed={plan_id,plan_version:'2',state:'accepted',coin:'BTC-EUR',symbol:'BTC-EUR',asset_id:'btc',ledger_version:'l1',financial_settings_version:'s1',
      held_quantity_at_acceptance:'0.8',core_quantity:'0.2',original_tactical_quantity:'0.6',rounding_residual_quantity:'0',accepted_at:'2026-01-06T00:00:00Z',
      replaces_plan_id:'old-plan',replacement_reason:replacement.replacement_reason,reviewed_execution_version:'1',source_market:{valid_until:'2099-01-01T00:00:00Z'},
      stages:['0.3','0.18','0.12'].map((quantity,i)=>({stage_id:plan_id+':'+(i+1),state:'unfinished',quantity,proportion_pct:replacement.proportions[i],level_eur:replacement.levels_eur[i]}))};
    assert.equal((await command('hosted_accept_crypto_plan',replacement,proposed)).state,'accepted');
    // An unrelated earlier BTC Asset has separate consumed capacity and is absent
    // from this Asset's ledger. It must not block the current Asset's plan.
    const unrelated={...old,plan_id:'other-asset-plan',asset_id:'other-btc'};
    await query("INSERT INTO hosted_crypto_plan_history VALUES('other-asset-plan','BTC-EUR','2025-01-01',$1::jsonb)",[JSON.stringify(unrelated)]);
    await db.exec(`INSERT INTO hosted_crypto_reports VALUES('unrelated-report','BTC-EUR','other-asset-plan','other-stage',0.1,'resolved','g1','unrelated-ledger','synthetic',now());
      INSERT INTO hosted_crypto_execution_capacity VALUES('unrelated-fill','other-btc',0.1,0.1,'{}');
      INSERT INTO hosted_crypto_match_allocations VALUES('unrelated-allocation','unrelated-match','BTC-EUR','other-asset-plan','other-stage','unrelated-report','unrelated-fill',0,0.1,'{}','unrelated-ledger',now())`);
    const read=async()=>(await query("SELECT hosted_read_crypto_executions('BTC-EUR') AS result"))[0].result;
    const accepted=await read();
    assert.equal(accepted.plan.plan_id,plan_id);assert.equal(accepted.progress.reconciliation_required,false);
    assert.equal(accepted.progress.reconciled_ledger_version,'l1');
    const receipt=accepted.allocations[0].receipt;
    assert.deepEqual(receipt,matched.receipt);
    for(const [id,apply] of [['corrected',next=>{next.ledger.disposals[0].fees_eur='2';next.ledger.disposals[0].realized_gain_eur='18';}],
                            ['reversed',next=>{next.ledger.disposals=[];next.ledger.positions[0].quantity='1';}]]){
      const next=structuredClone(model);next.ledger_version=id;apply(next);
      await query('INSERT INTO hosted_snapshot_generations VALUES($1,now(),\'synthetic\',$2::jsonb)',[id,JSON.stringify(next)]);
      await query('UPDATE hosted_snapshot_pointer SET generation_id=$1',[id]);
      const result=await read();
      assert.equal(result.progress.reconciliation_required,true,id);
      assert.equal(result.progress.reconciliation_reason,'execution_facts_changed_review');
      assert.equal(result.progress.reconciled_ledger_version,null);
      assert.equal(result.progress.matched_quantity,'0');
      assert.equal(result.allocations[0].quantity,'0.2');
      assert.deepEqual(result.allocations[0].receipt,receipt);
    }
    await db.exec("UPDATE hosted_snapshot_pointer SET generation_id='g1'");
    const restored=await read();
    assert.equal(restored.progress.reconciliation_required,false);
    assert.equal(restored.executions[0].available_quantity,'0');
    assert.deepEqual(restored.allocations[0].receipt,receipt);
  }finally{await db.close();}
});
