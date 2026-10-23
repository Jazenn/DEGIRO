// @vitest-environment jsdom
import { readFile } from 'node:fs/promises';
import { expect, test } from 'vitest';
// Browser workflow uses the actual static application, with only HTTP as a system boundary.
// @ts-expect-error plain browser JS deliberately has no bundled financial dependencies
import { loadSnapshot } from './public/app.js';

test('owner reads visibly labelled persisted synthetic values, versions and provenance', async () => {
  document.body.innerHTML = '<main id="snapshot"></main>';
  const read_model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  await loadSnapshot(document.querySelector('main'), async () => new Response(JSON.stringify({ state: 'ready', snapshot: {
    generation_id: 'synthetic-1', published_at: '2026-10-22T00:00:00Z', data_classification: 'synthetic', read_model,
  } })));
  expect(document.body.textContent).toContain('Synthetic data');
  expect(document.body.textContent).toContain('1100');
  expect(document.body.textContent).toContain('95');
  expect(document.body.textContent).toContain('synthetic-ledger-1');
  expect(document.body.textContent).toContain('synthetic-only');
});
test('owner sees distinct empty, expired-session, forbidden and failed-read states without replacement values', async () => {
  document.body.innerHTML = '<main></main>';
  const target = document.querySelector('main');
  for (const [status, payload, message] of [
    [200, { state: 'empty' }, 'No accepted Snapshot has been published.'],
    [401, {}, 'Your session has expired.'],
    [403, {}, 'Access is restricted to the owner.'],
    [503, { state: 'error' }, 'Snapshot unavailable.'],
  ] as const) {
    await loadSnapshot(target, async () => new Response(JSON.stringify(payload), { status }));
    expect(target?.textContent).toContain(message);
    expect(target?.textContent).not.toContain('EUR 0');
    expect(target?.textContent).not.toContain('Synthetic data');
  }
});

test('overview explains completed-sale gains, dated recorded charges and missing coverage without estimates', async () => {
  document.body.innerHTML = '<main></main>';
  const read_model = JSON.parse(await readFile('hosted/synthetic.fixture', 'utf8'));
  read_model.ledger.positions.push({ broker_asset_id: 'CLOSED', symbol: 'SOLD', asset_kind: 'ETF', quantity: '0', lots: [], retained_cost_eur: '0', cost_coverage: 'verified_complete', market_value_eur: '0', held_gain_eur: '0', realized_gain_eur: '45' });
  read_model.ledger.positions[0].held_gain_eur = null;
  read_model.ledger.positions[0].cost_coverage = 'missing_purchase_history';
  read_model.ledger.charges.push({ transaction_id: 'fee-2', date: '2026-01-09', category: 'connectivity', amount_eur: '2.50', allocation: 'portfolio' });
  read_model.ledger.diagnostics = ['missing_purchase_history'];
  await loadSnapshot(document.querySelector('main'), async () => new Response(JSON.stringify({ state: 'ready', snapshot: { generation_id: 'generation-costs', published_at: '2026-01-11T00:01:00Z', data_classification: 'private', read_model } })));
  const overview = document.querySelector('main')!;
  expect(overview.querySelector('[aria-label="Recorded charges"]')?.textContent).toContain('2026-01-09');
  expect(overview.querySelector('[aria-label="Recorded charges"]')?.textContent).toContain('connectivity');
  expect(overview.querySelector('[aria-label="Recorded charges"]')?.textContent).toContain('EUR 2.50');
  expect(overview.querySelector('[aria-label="Completed positions"]')?.textContent).toContain('EUR 45');
  expect(overview.querySelector('[aria-label="Current holdings"]')?.textContent).toContain('Unavailable');
  expect(overview.textContent).toContain('missing_purchase_history');
  expect(overview.textContent).toContain('already included');
  expect(overview.textContent).toContain('Future fee estimates');
  expect(overview.textContent).toContain('Finalized historical coverage is unavailable');
});
