import { readFile } from 'node:fs/promises';
import { expect, test } from 'vitest';
import { revalue } from './valuation';

test('revalues reconciled quantities coherently without changing costs, cash, realized results or history', async () => {
  const model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  model.portfolio_history = { finalized_cutoff: '2026-01-10' };
  const result = revalue(model, { version: '2', targets: [{ asset_id: 'SYNTHETIC-A', target_pct: '100' }] }, {
    SYNTHETIC: { price_eur: '1200.0000000000000001', observed_at: '2026-10-23T10:00:00Z', retrieved_at: '2026-10-23T10:00:01Z', provider: 'fixture', currency: 'EUR', adjustment_basis: 'unadjusted' },
  }, '2026-10-23T10:00:01Z');
  expect(result.ledger.market_value_eur).toBe('1200.0000000000000001');
  expect(result.ledger.net_gain_eur).toBe('195.0000000000000001');
  expect(result.ledger.attributed_gain_eur).toBe('195.0000000000000001');
  expect(result.ledger.positions[0].held_gain_eur).toBe('195.0000000000000001');
  expect(result.ledger.positions[0].lots).toEqual(model.ledger.positions[0].lots);
  expect(result.ledger.cash_balance_eur).toBe('0');
  expect(result.portfolio_history).toEqual(model.portfolio_history);
  expect(result.settings_version).toBe(model.settings_version);
  expect(result.rebalancing_targets_version).toBe('2');
  expect(result.contribution_inputs.positions[0].actual_pct).toBe('100');
  expect(model.ledger.market_value_eur).toBe('1100');
});

import { vi } from 'vitest';
import { createRefresh } from './refresh';

test('incomplete batches and ten-second timeout preserve the accepted generation', async () => {
  const model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  const accepted = { generation_id: 'before', published_at: '2026-01-11T00:00:00Z', data_classification: 'synthetic' as const, read_model: model };
  let published = false;
  const store = { read: async () => ({ snapshot: accepted, settings: { version: '2', targets: [] }, mappings: [{ symbol: 'SYNTHETIC', provider: 'yahoo' as const, provider_symbol: 'EXAMPLE', evidence: 'fixture' }] }),
    publish: async () => { published = true; return true; } };
  const failed = createRefresh(store, async () => { throw Error('provider secret details'); });
  expect(await failed()).toEqual({ state: 'retained', reason: 'refresh_failed', generation_id: 'before' });
  expect(published).toBe(false);
  vi.useFakeTimers();
  try {
    const hanging = createRefresh(store, async () => new Promise(() => {}));
    const operation = hanging();
    await vi.advanceTimersByTimeAsync(10000);
    expect(await operation).toEqual({ state: 'retained', reason: 'refresh_timeout', generation_id: 'before' });
    expect(published).toBe(false);
  } finally { vi.useRealTimers(); }
});

test('stale crypto prices never become eligible merely because retrieved now, and unknown times reject refresh', async () => {
  const model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  model.ledger.positions[0].asset_kind = 'Cryptocurrency';
  const quote = { price_eur: '1100', observed_at: '2026-10-23T09:54:59Z', retrieved_at: '2026-10-23T10:00:00Z', provider: 'fixture', currency: 'EUR' as const, adjustment_basis: 'unadjusted' as const };
  const settings = { version: '1', targets: [] };
  expect(revalue(model, settings, { SYNTHETIC: quote }, '2026-10-23T10:00:00Z').crypto_quote_eligibility.SYNTHETIC).toBe('stale');
  expect(revalue(model, settings, { SYNTHETIC: { ...quote, observed_at: '2026-10-23T09:55:00Z' } }, '2026-10-23T10:00:00Z').crypto_quote_eligibility.SYNTHETIC).toBe('eligible');
  expect(() => revalue(model, settings, { SYNTHETIC: { ...quote, observed_at: null } }, '2026-10-23T10:00:00Z')).toThrow('incomplete_quote_batch');
  model.ledger.net_gain_eur = null; model.ledger.positions[0].held_gain_eur = null;
  const result = revalue(model, settings, { SYNTHETIC: quote }, '2026-10-23T10:00:00Z');
  expect(result.ledger.net_gain_eur).toBeNull();
  expect(result.ledger.positions[0].held_gain_eur).toBeNull();
});

test('complete refresh uses at most four concurrent providers and short cache avoids another quote batch', async () => {
  const model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  model.ledger.positions = Array.from({ length: 7 }, (_, i) => ({ ...model.ledger.positions[0], symbol: 'ASSET'+i, broker_asset_id: 'ID'+i }));
  model.ledger.market_value_eur = '7700';
  let input = { snapshot: { generation_id: 'before', published_at: '2026-10-23T10:00:00Z', data_classification: 'synthetic' as const, read_model: model },
    settings: { version: '2', targets: [] }, mappings: model.ledger.positions.map((p: any) => ({ symbol: p.symbol, provider: 'yahoo' as const, provider_symbol: p.symbol, evidence: 'fixture' })) };
  let active = 0, maximum = 0, requests = 0;
  const refresh = createRefresh({ read: async () => input, publish: async (_input, updated, id) => { input = { ...input, snapshot: { ...input.snapshot, generation_id: id, read_model: updated } }; return true; } }, async () => {
    active++; requests++; maximum = Math.max(maximum, active); await new Promise(resolve => setTimeout(resolve, 1)); active--;
    return { price_eur: '1200', observed_at: '2026-10-23T10:00:00Z', retrieved_at: '2026-10-23T10:00:00Z', provider: 'fixture', currency: 'EUR', adjustment_basis: 'unadjusted' };
  }, () => Date.parse('2026-10-23T10:00:01Z'));
  expect((await refresh()).state).toBe('refreshed');
  expect(maximum).toBe(4);
  expect(requests).toBe(7);
  expect((await refresh()).state).toBe('cached');
  expect(requests).toBe(7);
});

import { valuationStore } from './valuation-store';
import { fetchQuote } from './quote-provider';

test('database refresh wire returns canonical UTC timestamp and rejects malformed persisted metadata', async () => {
  const read_model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  const row = { generation_id: 'g1', published_at: '2026-10-23T10:00:00.000000Z', data_classification: 'synthetic', read_model,
    rebalancing_targets_version: '2', targets: [], mappings: [] };
  const store = valuationStore(async () => [row]);
  expect((await store.read(new AbortController().signal))?.snapshot.published_at).toBe('2026-10-23T10:00:00.000000Z');
  row.rebalancing_targets_version = 'corrupt';
  await expect(store.read(new AbortController().signal)).rejects.toThrow('invalid_snapshot');
});

test('provider prices retain decimal lexemes and actual trade observation times independently of retrieval', async () => {
  const signal = new AbortController().signal;
  const crypto = await fetchQuote({ symbol: 'BTC', provider: 'binance', provider_symbol: 'BTCEUR', evidence: 'verified fixture' }, signal,
    async () => Response.json([{ p: '100000.0000000000000001', T: 1792749600000 }]));
  expect(crypto.price_eur).toBe('100000.0000000000000001');
  expect(crypto.observed_at).toBe('2026-10-23T10:00:00.000Z');
  const etf = await fetchQuote({ symbol: 'ETF', provider: 'yahoo', provider_symbol: 'TEST.DE', evidence: 'verified fixture' }, signal,
    async () => new Response('{"chart":{"result":[{"meta":{"currency":"EUR","symbol":"TEST.DE","regularMarketPrice":123.0000000000000001,"regularMarketTime":1792749600}}]}}'));
  expect(etf.price_eur).toBe('123.0000000000000001');
});
import { createApplication } from './application';
import { databaseTransport, env, login } from './auth-test-support';

test('current refresh is owner authenticated and same-origin before any provider work', async () => {
  let calls = 0;
  const app = createApplication({ readAccepted: async () => null, authQuery: databaseTransport(), refresh: async () => { calls++; return { state: 'retained', reason: 'refresh_failed' }; } });
  const headers = { Cookie: (await login()).session!, Origin: env.APP_ORIGIN };
  const call = (method: string, requestHeaders = headers) => app(new Request(env.APP_ORIGIN+'/api/refresh', { method, headers: requestHeaders }), env);
  expect((await call('POST', { ...headers, Cookie: '' })).status).toBe(401);
  expect((await call('POST', { ...headers, Origin: 'https://wrong.test' })).status).toBe(403);
  expect((await call('GET')).status).toBe(405);
  expect(calls).toBe(0);
  const response = await call('POST');
  expect(response.status).toBe(200);
  expect(response.headers.get('cache-control')).toBe('private, no-store');
  expect(await response.json()).toEqual({ state: 'retained', reason: 'refresh_failed' });
  expect(calls).toBe(1);
});

import Decimal from 'decimal.js';
test('fast revaluation matches canonical FIFO ledger after partial sale, fees, reinvestment, income and cash', async () => {
  // Fixture records source CSV/settings and before/after outputs from calculate_portfolio.
  const fixture = JSON.parse(await readFile('tests/fixtures/revaluation-canonical.fixture', 'utf8'));
  const next = revalue(fixture.before, { version: '2', targets: [] }, fixture.after.observed_prices, '2026-01-11T00:00:00Z');
  for (const field of ['cash_balance_eur','net_external_contributions_eur','market_value_eur','equity_eur','net_gain_eur','attributed_gain_eur','net_income_eur','portfolio_costs_eur']) {
    expect(new Decimal(next.ledger[field]).eq(fixture.after.ledger[field]), field).toBe(true);
  }
  for (let i = 0; i < next.ledger.positions.length; i++) {
    for (const field of ['quantity','retained_cost_eur','market_value_eur','held_gain_eur','realized_gain_eur'])
      expect(new Decimal(next.ledger.positions[i][field]).eq(fixture.after.ledger.positions[i][field]), field).toBe(true);
    expect(next.ledger.positions[i].lots).toEqual(fixture.after.ledger.positions[i].lots);
  }
  expect(next.ledger.net_gain_eur).toBe('503');
});


import { validReadModel } from './read-model';
test('current target-version refresh keeps finalized historical settings and cutoff unchanged', async () => {
  const model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  model.portfolio_history = { schema_version:'observed-history-v1', ledger_version:model.ledger_version, settings_version:'historical-evidence', cutoff:'2026-01-11T00:00:00Z', periods:{}, diagnostics:['missing_observed_history'] };
  const next = revalue(model, { version:'2', targets:[] }, { SYNTHETIC: { price_eur:'1200', observed_at:'2026-10-23T10:00:00Z', retrieved_at:'2026-10-23T10:00:01Z',provider:'synthetic',currency:'EUR',adjustment_basis:'unadjusted' } },'2026-10-23T10:00:01Z');
  expect(next.settings_version).toBe(model.settings_version);
  expect(next.rebalancing_targets_version).toBe('2');
  expect(next.portfolio_history).toEqual(model.portfolio_history);
  expect(validReadModel(next)).toBe(true);
});

test('current quote refresh preserves financial settings identity while versioning shared targets separately', async()=>{
  const model=JSON.parse(await readFile('hosted/synthetic.fixture','utf8'));
  model.settings_version='financial-evidence-hash';model.rebalancing_targets_version='1';
  const next=revalue(model,{version:'2',targets:[]},{SYNTHETIC:{price_eur:'1200',observed_at:'2026-10-23T10:00:00Z',retrieved_at:'2026-10-23T10:00:01Z',provider:'synthetic',currency:'EUR',adjustment_basis:'unadjusted'}},'2026-10-23T10:00:01Z');
  expect(next.settings_version).toBe('financial-evidence-hash');
  expect(next.rebalancing_targets_version).toBe('2');
  expect(next.contribution_inputs.settings_version).toBe('financial-evidence-hash');
  expect(next.contribution_inputs.rebalancing_targets_version).toBe('2');
});

test('current quote refresh preserves record timing without manufacturing broker coverage',async()=>{
  const model=JSON.parse(await readFile('hosted/synthetic.fixture','utf8'));
  const next=revalue(model,{version:'2',targets:[]},{SYNTHETIC:{price_eur:'1200',observed_at:'2026-10-23T10:00:00Z',retrieved_at:'2026-10-23T10:00:01Z',provider:'synthetic',currency:'EUR',adjustment_basis:'unadjusted'}},'2026-10-23T10:00:01Z');
  expect(next.cutoff).toBe('2026-10-23T10:00:01Z');
  expect(next.ledger_cutoff).toBe('2026-01-11T00:00:00+00:00');
  expect(next.latest_recorded_transaction_at).toBe('2026-01-03T09:01:00+00:00');
  expect(next.source_coverage_through).toBeNull();
});
