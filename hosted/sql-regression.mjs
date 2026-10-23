// Actual PostgreSQL execution: isolated WebAssembly database, no external service or credentials.
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { test } from 'node:test';

const source = name => readFile(new URL(`./${name}.sql`, import.meta.url), 'utf8');

test('PostgreSQL target retries and valuation publication preserve immutable ledger facts', async () => {
  const db = new PGlite();
  try {
    for (const name of ['schema', 'targets-schema', 'import-schema', 'valuation-schema']) await db.exec(await source(name));
    const query = async (sql, params = []) => (await db.query(sql, params)).rows;
    const targets = [{ asset_id: 'SYNTHETIC-A', target_pct: '100' }];
    const save = async (id, version, value = targets) => (await query('SELECT hosted_save_targets($1,$2,$3::jsonb) AS result', [id,version,JSON.stringify(value)]))[0].result;
    const saved = await save('first-operation', 0);
    assert.equal(saved.state, 'saved');
    assert.deepEqual(await save('first-operation', 0), saved);
    assert.equal((await save('stale-operation', 0)).state, 'conflict');
    assert.equal((await save('first-operation', 1)).state, 'conflict');
    await assert.rejects(save('invalid-operation', 1, [{ asset_id: 'SYNTHETIC-A', target_pct: '99' }]), /Invalid targets/);
    const model = JSON.parse(await readFile(new URL('./synthetic.fixture', import.meta.url), 'utf8'));
    model.rebalancing_targets_version = '1';
    await query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('original','synthetic',$1::jsonb)",[JSON.stringify(model)]);
    await db.exec("INSERT INTO hosted_snapshot_pointer VALUES(true,'original')");
    await assert.rejects(db.exec("UPDATE hosted_snapshot_generations SET published_at=now() WHERE generation_id='original'"), /immutable/);
    const publish = async (id, expected, version, value, deadline = '2099-01-01T00:00:00Z') =>
      (await query('SELECT hosted_publish_valuation($1,$2,$3,$4::jsonb,$5::timestamptz) AS result',[id,expected,version,JSON.stringify(value),deadline]))[0].result;
    assert.equal(await publish('stale-generation','missing',1,model),false);
    assert.equal(await publish('stale-targets','original',0,model),false);
    assert.equal(await publish('expired','original',1,model,'2000-01-01T00:00:00Z'),false);
    const next = structuredClone(model);
    next.cutoff = '2026-10-23T10:00:01Z';
    Object.assign(next.ledger,{ market_value_eur:'1200',equity_eur:'1200',net_gain_eur:'195',attributed_gain_eur:'195' });
    Object.assign(next.ledger.positions[0],{ market_value_eur:'1200',held_gain_eur:'195' });
    next.observed_prices.SYNTHETIC.price_eur = '1200';
    // Valid refresh reaches every JSONB invariant; a mocked SQL transport missed precedence errors here.
    assert.equal(await publish('refreshed','original',1,next),true);
    const immutableEdits = [
      value => { value.settings_version = 'changed-financial-settings'; },
      value => { value.ledger.cash_balance_eur = '1'; },
      value => { value.ledger.net_external_contributions_eur = '1'; },
      value => { value.ledger.positions[0].quantity = '2'; },
      value => { value.ledger.positions[0].lots[0].cost_eur = '0'; },
      value => { value.ledger.positions[0].realized_gain_eur = '100'; },
      value => { value.ledger_cutoff = value.cutoff; },
      value => { value.portfolio_history = { settings_version:'invented' }; },
    ];
    for (const [index, edit] of immutableEdits.entries()) {
      const invalid = structuredClone(next); edit(invalid);
      await assert.rejects(publish('invalid-'+index,'refreshed',1,invalid), /Inconsistent valuation/);
    }
    assert.equal((await query('SELECT generation_id FROM hosted_snapshot_pointer'))[0].generation_id,'refreshed');
    assert.equal((await query("SELECT count(*)::text AS count FROM hosted_snapshot_generations"))[0].count,'2');
    const permissions = await query("SELECT has_function_privilege('public',oid,'EXECUTE') AS allowed FROM pg_proc WHERE proname IN ('hosted_save_targets','hosted_publish_valuation')");
    assert.equal(permissions.length,2); assert.ok(permissions.every(row => !row.allowed));
    await db.exec(`CREATE ROLE synthetic_worker;
      GRANT SELECT ON hosted_targets,hosted_snapshot_pointer,hosted_snapshot_generations TO synthetic_worker;
      GRANT SELECT(job_id,state,history_state,attempts,diagnostics,generation_id,created_at,updated_at) ON hosted_import_jobs TO synthetic_worker;
      GRANT EXECUTE ON FUNCTION hosted_save_targets(text,bigint,jsonb),hosted_publish_valuation(text,text,bigint,jsonb,timestamptz) TO synthetic_worker;
      SET ROLE synthetic_worker`);
    assert.equal((await save('worker-role-save',1)).current.version,'2');
    const permitted = structuredClone(next); permitted.rebalancing_targets_version = '2';
    assert.equal(await publish('worker-refreshed','refreshed',2,permitted),true);
    await assert.rejects(db.exec("UPDATE hosted_snapshot_pointer SET generation_id='original'"), /permission denied/);
    await assert.rejects(db.exec("UPDATE hosted_targets SET version=999"), /permission denied/);
    await assert.rejects(db.exec('SELECT csv_content FROM hosted_import_jobs'), /permission denied/);
    await assert.rejects(db.exec('SELECT * FROM hosted_target_operations'), /permission denied/);
    await db.exec('RESET ROLE; CREATE ROLE synthetic_outsider; SET ROLE synthetic_outsider');
    await assert.rejects(save('outside-role',2), /permission denied/);
    await assert.rejects(db.exec('SELECT read_model FROM hosted_snapshot_generations'), /permission denied/);
    await db.exec('RESET ROLE');
  } finally { await db.close(); }
});

test('PostgreSQL crypto plan acceptance retains history, retries safely and isolates coins', async () => {
  const db = new PGlite();
  try {
    for (const name of ['schema','targets-schema','contribution-schema','crypto-market-schema','crypto-plan-schema']) await db.exec(await source(name));
    const query = async (sql, params = []) => (await db.query(sql, params)).rows;
    const now = new Date().toISOString(), end = '2099-01-01T00:00:00Z';
    const model = { calculation_version:'decimal-accounting-v1',ledger_version:'synthetic-ledger',settings_version:'synthetic-financial',
      ledger:{schema_version:'ledger-v1',positions:[{broker_asset_id:'synthetic-btc',symbol:'BTC-EUR',asset_kind:'Cryptocurrency',cost_coverage:'verified_complete',quantity:'1'}]} };
    await query("INSERT INTO hosted_snapshot_generations VALUES('synthetic',now(),'synthetic',$1::jsonb)",[JSON.stringify(model)]);
    await db.exec(`INSERT INTO hosted_snapshot_pointer VALUES(true,'synthetic');
      INSERT INTO hosted_execution_terms VALUES('synthetic-btc','quantity1',0.01,0.01,0,0,0,0,'known','all_purchase_charges','EUR','SYNTHETIC ONLY','2000-01-01','2099-01-01');
      INSERT INTO hosted_crypto_sale_permissions VALUES('BTC-EUR','synthetic-btc','BTC-EUR','sale1','quantity1',true,'SYNTHETIC ONLY','2000-01-01','2099-01-01');
      INSERT INTO hosted_crypto_market_history VALUES('BTC-EUR','market1','{}',now(),'[]')`);
    const request = { coin:'BTC-EUR',operation_id:'synthetic-op-1',generation_id:'synthetic',expected_version:'0',core_quantity:'0.2',
      proportions:['50','30','20'],levels_eur:['100','200','300'],terms_revision:'sale1',market_version:'market1' };
    const plan = { plan_id:'plan-synthetic-op-1',plan_version:'1',coin:'BTC-EUR',asset_id:'synthetic-btc',ledger_version:'synthetic-ledger',
      financial_settings_version:'synthetic-financial',held_quantity_at_acceptance:'1',core_quantity:'0.2',original_tactical_quantity:'0.8',rounding_residual_quantity:'0',
      accepted_at:now,source_market:{valid_until:end},stages:['0.4','0.24','0.16'].map((quantity,i)=>({stage_id:`plan-synthetic-op-1:${i+1}`,state:'unfinished',quantity,proportion_pct:request.proportions[i],level_eur:request.levels_eur[i]})) };
    const accept = async value => (await query('SELECT hosted_accept_crypto_plan($1::jsonb,$2::jsonb) AS result',[JSON.stringify(value),JSON.stringify(plan)]))[0].result;
    const first = await accept(request); assert.equal(first.state,'accepted'); assert.equal(first.plan.core_quantity,'0.2');
    assert.deepEqual(await accept(request),first);
    assert.equal((await accept({...request,core_quantity:'0.3'})).reason,'operation_id_reused');
    assert.equal((await accept({...request,operation_id:'synthetic-op-2'})).state,'conflict');
    assert.equal((await accept({...request,operation_id:'synthetic-op-3',expected_version:'1'})).state,'replacement_required');
    assert.equal((await query("SELECT version::text FROM hosted_crypto_plan_state WHERE coin='ETH-EUR'"))[0].version,'0');
    assert.equal((await query('SELECT count(*)::text AS count FROM hosted_crypto_plan_history'))[0].count,'1');
    await db.exec(`CREATE ROLE synthetic_plan_worker;
      GRANT SELECT ON hosted_crypto_plan_state,hosted_crypto_sale_permissions TO synthetic_plan_worker;
      GRANT EXECUTE ON FUNCTION hosted_accept_crypto_plan(jsonb,jsonb) TO synthetic_plan_worker;
      SET ROLE synthetic_plan_worker`);
    assert.deepEqual(await accept(request),first);
    await assert.rejects(db.exec("UPDATE hosted_crypto_plan_state SET version=999 WHERE coin='BTC-EUR'"),/permission denied/);
    await assert.rejects(db.exec('DELETE FROM hosted_crypto_plan_history'),/permission denied/);
    await db.exec('RESET ROLE');
    assert.equal((await query("SELECT has_function_privilege('public','hosted_accept_crypto_plan(jsonb,jsonb)','EXECUTE') AS allowed"))[0].allowed,false);
  } finally { await db.close(); }
});
