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
