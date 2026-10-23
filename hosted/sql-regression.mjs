// Actual PostgreSQL execution: isolated WebAssembly database, no external service or credentials.
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { test } from 'node:test';

const source = name => readFile(new URL(`./${name}.sql`, import.meta.url), 'utf8');

test('PostgreSQL target retries and valuation publication preserve immutable ledger facts', async () => {
  const db = new PGlite();
  try {
    for (const name of ['schema', 'targets-schema', 'valuation-schema']) await db.exec(await source(name));
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
  } finally { await db.close(); }
});
