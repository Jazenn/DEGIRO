// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
// @ts-expect-error deployed browser module
import { renderPerformance } from './public/performance.js';

const start = '2026-01-01T00:00:00Z', end = '2026-01-05T00:00:00Z';
const snapshot = { generation_id: 'g1', read_model: {} };
function period() {
  return { state: 'ready', start, end, shorter_coverage: false,
    points: ['1000', '1010', '1020', '1030', '1047'].map((equity_eur, index) => ({ cutoff: `2026-01-0${index + 1}T00:00:00Z`, equity_eur })),
    estimated_return: { state: 'ready', percent: '4.7', cutoff: end, method: 'geometrically_linked_daily_modified_dietz' },
    attribution: { retained_gain_change_eur: '0', realized_gain_change_eur: '46', net_income_eur: '3', portfolio_costs_eur: '2', net_external_flows_eur: '0', net_gain_eur: '47' },
    assets: [{ symbol: 'SOLD', realized_gain_change_eur: '46', retained_gain_change_eur: '0' }], diagnostics: [] };
}
const envelope = (selected = 'ALL', value: any = period()) => ({ state: 'ready', generation_id: 'g1', period_name: selected,
  cutoff: end, ledger_version: 'source-ledger', settings_version: 'history-settings', periods: {}, period: value });
function mount() { const target = document.createElement('section'); document.body.replaceChildren(target); return target; }
afterEach(() => { document.querySelector('section')?.remove(); window.history.replaceState(null, '', '#snapshot'); });

test('period chart and result load only when opened and share pinned observed endpoints', async () => {
  window.history.replaceState(null, '', '#snapshot');
  const target = mount(), requests: string[] = [];
  renderPerformance(target, snapshot, async (url: string) => { requests.push(url); return Response.json(envelope()); });
  expect(requests).toEqual([]);
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === 'Load finalized history')!.click();
  await vi.waitFor(() => expect(target.textContent).toContain('EUR 47'));
  expect(requests).toEqual(['/api/history?generation_id=g1&period=ALL']);
  expect(target.textContent).toContain('Estimated cash-flow-adjusted return: 4.7%');
  expect(target.textContent).toContain('Finalized percentage cutoff: ' + end);
  expect(target.querySelector('svg')?.getAttribute('aria-label')).toContain(start);
  expect(target.querySelector('svg')?.getAttribute('aria-label')).toContain(end);
  expect(target.textContent).toContain('SOLD');
});

test('valid unavailable periods explain shorter coverage without keeping the previous chart', async () => {
  window.history.replaceState(null, '', '#performance');
  const target = mount();
  await renderPerformance(target, snapshot, async (url: string) => Response.json(url.includes('period=1Y')
    ? envelope('1Y', { state: 'unavailable', start, end, shorter_coverage: true, points: [], diagnostics: ['missing_observed_price:ETF'] }) : envelope()));
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1Y')!.click();
  await vi.waitFor(() => expect(target.textContent).toContain('Shorter observed coverage'));
  expect(target.textContent).toContain('missing_observed_price:ETF');
  expect(target.textContent).toContain('Estimated cash-flow-adjusted return unavailable');
  expect(target.textContent).not.toContain('4.7%');
  expect(target.querySelector('svg')).toBeNull();
});

test('failed or mismatched generation reads preserve the prior period and its original labels', async () => {
  window.history.replaceState(null, '', '#performance');
  const target = mount(); let count = 0;
  await renderPerformance(target, snapshot, async () => ++count === 1 ? Response.json(envelope()) : count === 2 ? Response.json({ ...envelope('1Y'), generation_id: 'another-generation' }) : Response.json({}, { status: 503 }));
  const chart = target.querySelector('svg');
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1Y')!.click();
  await vi.waitFor(() => expect(target.textContent).toContain('previous displayed period'));
  expect(target.querySelector('svg')).toBe(chart);
  expect(target.textContent).toContain('All time | ' + start);
  expect(target.textContent).not.toContain('1Y |');
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1M')!.click();
  await vi.waitFor(() => expect(count).toBe(3));
  expect(target.querySelector('svg')).toBe(chart);
});

test('first-funded return opening stays distinct and audit pages fetch only on expansion', async () => {
  window.history.replaceState(null, '', '#performance');
  const target = mount(), requests: string[] = [], value = period();
  Object.assign(value.estimated_return, { opening_coverage: 'first_funded_baseline', start: '2026-01-03T00:00:00Z' });
  await renderPerformance(target, snapshot, async (url: string) => {
    requests.push(url);
    if (url.includes('offset=')) return Response.json({ state: 'ready', generation_id: 'g1', period_name: 'ALL', ledger_version: 'source-ledger', settings_version: 'history-settings',
      offset: '0', next_offset: null, points: [{ cutoff: start, equity_eur: '1000', observed_prices: { FUND: { provider: 'dated-source', observed_at: start, retrieved_at: end, currency: 'EUR', adjustment_basis: 'unadjusted' } } }],
      daily: [{ start, cutoff: end, net_gain_eur: '47', external_flows_eur: '0', weighted_external_flows_eur: '0', denominator_eur: '1000', fraction: '0.047', flows: [{ transaction_id: 'source-flow', at: start, amount_eur: '500', remaining_interval_weight: '0.5' }] }] });
    return Response.json(envelope('ALL', value));
  });
  expect(target.textContent).toContain('Percentage opening: 2026-01-03T00:00:00Z');
  expect(target.textContent).toContain('Verified zero-capital prefunding intervals');
  expect(requests).toHaveLength(1);
  const details = target.querySelector('details')!; details.open = true; details.dispatchEvent(new Event('toggle'));
  await vi.waitFor(() => expect(target.textContent).toContain('dated-source'));
  expect(requests[1]).toBe('/api/history?generation_id=g1&period=ALL&offset=0');
  expect(target.textContent).toContain('remaining interval weight 0.5');
  expect(target.textContent).toContain('source-flow');
});

test('missing history never creates a zero or demonstration chart', async () => {
  window.history.replaceState(null, '', '#performance');
  const target = mount();
  await renderPerformance(target, snapshot, async () => Response.json({ state: 'unavailable', generation_id: 'g1', reason: 'history_not_supplied' }));
  expect(target.textContent).toContain('Observed history unavailable');
  expect(target.textContent).not.toContain('EUR 0');
  expect(target.querySelector('svg')).toBeNull();
});

test('late period responses cannot replace a newer selection or a newly accepted generation', async () => {
  window.history.replaceState(null, '', '#performance');
  const target = mount(), releases: ((value: Response) => void)[] = [];
  await renderPerformance(target, snapshot, async (url: string) => url.includes('period=1Y')
    ? new Promise<Response>(resolve => { releases.push(resolve); }) : Response.json(envelope(url.includes('period=1M') ? '1M' : 'ALL')));
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1Y')!.click();
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1M')!.click();
  await vi.waitFor(() => expect(target.textContent).toContain('1M | ' + start));
  releases[0](Response.json(envelope('1Y')));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(target.textContent).toContain('1M | ' + start);
  Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1Y')!.click();
  await renderPerformance(target, { ...snapshot, generation_id: 'g2' }, async () => Response.json({ ...envelope('1M'), generation_id: 'g2' }));
  releases[1](Response.json(envelope('1Y')));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(target.textContent).toContain('1M | ' + start);
  expect(target.textContent).not.toContain('1Y |');
  expect(target.querySelector('[data-history-view]')?.getAttribute('data-generation')).toBe('g2');
});
