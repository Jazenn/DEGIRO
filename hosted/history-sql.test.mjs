import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { test } from 'vitest';
import { NeonSnapshotStore } from './snapshot-store.ts';
import { valuationStore } from './valuation-store.ts';
import { historyStore } from './history-store.ts';

const source = name => readFile(new URL(`./${name}.sql`, import.meta.url), 'utf8');
const modelFixture = async () => {
  const model = JSON.parse(await readFile(new URL('./synthetic.fixture', import.meta.url), 'utf8'));
  model.portfolio_history = { schema_version: 'observed-history-v1', ledger_version: model.ledger_version,
    settings_version: 'history-settings', cutoff: '2026-01-11T00:00:00Z', periods: {}, diagnostics: ['history_not_supplied'] };
  return model;
};
test('current Snapshot reads omit immutable Portfolio History at the database seam', async () => {
  const db = new PGlite();
  try {
    await db.exec(await source('schema'));
    const model = await modelFixture();
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('original','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    await db.exec("INSERT INTO hosted_snapshot_pointer VALUES(true,'original')");
    const store = new NeonSnapshotStore(async (sql, params) => (await db.query(sql, params)).rows);
    const accepted = await store.readAccepted();
    assert.equal(accepted.generation_id, 'original');
    assert.equal('portfolio_history' in accepted.read_model, false);
    assert.deepEqual(accepted.read_model.ledger, model.ledger);
  } finally { await db.close(); }
});
test('history reads pin one generation and period while source and return audits are paged', async () => {
  const db = new PGlite();
  try {
    await db.exec(await source('schema'));
    const model = await modelFixture();
    const points = Array.from({ length: 10 }, (_, index) => ({ cutoff: `2026-01-${String(index + 1).padStart(2, '0')}T00:00:00Z`, equity_eur: index === 9 ? '1100' : '1000', diagnostics: [],
      observed_prices: { FUND: { price_eur: index === 9 ? '110' : '100', observed_at: `2026-01-${String(index + 1).padStart(2, '0')}T00:00:00Z`, retrieved_at: '2026-01-11T00:00:00Z', provider: 'invented daily source', currency: 'EUR', adjustment_basis: 'unadjusted' } } }));
    const period = { state: 'ready', start: points[0].cutoff, end: points.at(-1).cutoff, requested_start: points[0].cutoff, shorter_coverage: false, diagnostics: [], points,
      attribution: { retained_gain_change_eur: '100', realized_gain_change_eur: '0', net_income_eur: '0', portfolio_costs_eur: '0', net_external_flows_eur: '0', net_gain_eur: '100' }, assets: [],
      estimated_return: { state: 'ready', method: 'geometrically_linked_daily_modified_dietz', start: points[0].cutoff, cutoff: points.at(-1).cutoff, percent: '10', diagnostics: [],
        daily: points.slice(1).map((point, index) => ({ start: points[index].cutoff, cutoff: point.cutoff, net_gain_eur: index === 8 ? '100' : '0', external_flows_eur: '0', weighted_external_flows_eur: '0', denominator_eur: '1000', fraction: index === 8 ? '0.1' : '0', flows: [] })) } };
    model.portfolio_history = { schema_version: 'observed-history-v1', ledger_version: model.ledger_version, settings_version: 'historical-source-settings', cutoff: points.at(-1).cutoff,
      source_timezone: { name: 'Europe/Amsterdam', status: 'owner_assumed', evidence: 'invented policy' }, periods: Object.fromEntries(['ALL', 'YTD', '1Y', '3M', '1M', '1W'].map(name => [name, period])) };
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('historical','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    const reader = historyStore(async (sql, params) => (await db.query(sql, params)).rows);
    const summary = await reader.read({ generation_id: 'historical', period: 'ALL' });
    assert.equal(summary.generation_id, 'historical');
    assert.equal(summary.period_name, 'ALL');
    assert.equal(summary.settings_version, 'historical-source-settings');
    assert.equal(Object.keys(summary.periods).length, 6);
    assert.equal(summary.period.points.length, 10);
    assert.deepEqual(summary.period.points.at(-1), { cutoff: '2026-01-10T00:00:00Z', equity_eur: '1100' });
    assert.equal('daily' in summary.period.estimated_return, false);
    assert.equal(summary.source_timezone.status, 'owner_assumed');
    const detail = await reader.read({ generation_id: 'historical', period: 'ALL', offset: '0' });
    assert.equal(detail.points.length, 7);
    assert.equal(detail.points[0].observed_prices.FUND.provider, 'invented daily source');
    assert.equal(detail.daily.length, 6);
    assert.equal(detail.next_offset, '7');
    const next = await reader.read({ generation_id: 'historical', period: 'ALL', offset: detail.next_offset });
    assert.equal(next.points.length, 3);
    assert.equal(next.daily.at(-1).fraction, '0.1');
    assert.equal(next.next_offset, null);
    assert.equal((await reader.read({ generation_id: 'missing', period: 'ALL' })).reason, 'generation_unavailable');
    await assert.rejects(reader.read({ generation_id: 'historical', period: 'arbitrary' }), /invalid_history_request/);
    period.points[0].observed_prices.FUND.price_eur = 100;
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('corrupt-audit','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    await assert.rejects(reader.read({ generation_id: 'corrupt-audit', period: 'ALL', offset: '0' }), /invalid_history/);
    period.estimated_return.start = points[1].cutoff;
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('wrong-opening','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    await assert.rejects(reader.read({ generation_id: 'wrong-opening', period: 'ALL' }), /invalid_history/);
    Object.assign(period.estimated_return, { opening_coverage: 'first_funded_baseline', requested_start: period.start, excluded_prefunding_intervals: [points[1].cutoff] });
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('first-funded','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    assert.equal((await reader.read({ generation_id: 'first-funded', period: 'ALL' })).period.estimated_return.start, points[1].cutoff);
    period.estimated_return.excluded_prefunding_intervals = ['not-a-midnight'];
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('bad-prefunding','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    await assert.rejects(reader.read({ generation_id: 'bad-prefunding', period: 'ALL' }), /invalid_history/);
  } finally { await db.close(); }
});
test('a lean current refresh preserves server-owned history and rejects replacement history', async () => {
  const db = new PGlite();
  try {
    for (const name of ['schema', 'targets-schema', 'contribution-schema', 'mixed-contribution-schema', 'valuation-schema']) await db.exec(await source(name));
    const model = await modelFixture();
    await db.query("INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES('original','synthetic',$1::jsonb)", [JSON.stringify(model)]);
    await db.exec("INSERT INTO hosted_snapshot_pointer VALUES(true,'original')");
    const store = valuationStore(async (sql, params) => (await db.query(sql, params)).rows);
    const signal = new AbortController().signal;
    const input = await store.read(signal);
    assert.equal('portfolio_history' in input.snapshot.read_model, false);
    const next = structuredClone(input.snapshot.read_model);
    next.rebalancing_targets_version = input.settings.version;
    next.cutoff = '2026-10-23T10:00:01Z';
    assert.equal(await store.publish(input, next, 'refreshed', '2099-01-01T00:00:00Z', signal), true);
    const persisted = (await db.query("SELECT read_model FROM hosted_snapshot_generations WHERE generation_id='refreshed'")).rows[0].read_model;
    assert.deepEqual(persisted.portfolio_history, model.portfolio_history);
    assert.equal(persisted.ledger_version, model.ledger_version);
    assert.equal(persisted.settings_version, model.settings_version);
    const accepted = await store.read(signal);
    await assert.rejects(store.publish(accepted, { ...next, portfolio_history: { ...model.portfolio_history, settings_version: 'forged' } }, 'forged', '2099-01-01T00:00:00Z', signal), /Inconsistent valuation/);
    assert.equal(await store.publish(input, next, 'stale', '2099-01-01T00:00:00Z', signal), false);
  } finally { await db.close(); }
});
