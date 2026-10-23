// @vitest-environment jsdom
import { expect, test } from 'vitest';
// @ts-expect-error deployed browser module
import { renderPerformance } from './public/performance.js';

test('period chart and result use the same explicit observed endpoints and mark shorter coverage', () => {
  const target = document.createElement('section');
  renderPerformance(target, { generation_id: 'g1', read_model: { portfolio_history: {
    cutoff: '2026-01-05T00:00:00Z', periods: { ALL: { state: 'ready', start: '2026-01-01T00:00:00Z', end: '2026-01-05T00:00:00Z', shorter_coverage: false,
      points: [{ cutoff: '2026-01-01T00:00:00Z', equity_eur: '1000', observed_prices: {} }, { cutoff: '2026-01-05T00:00:00Z', equity_eur: '1047', observed_prices: {} }],
      estimated_return: { state: 'ready', percent: '10', cutoff: '2026-01-05T00:00:00Z', method: 'geometrically_linked_daily_modified_dietz', daily: [] }, attribution: { retained_gain_change_eur: '0', realized_gain_change_eur: '46', net_income_eur: '3', portfolio_costs_eur: '2', net_external_flows_eur: '0', net_gain_eur: '47' }, assets: [{ symbol: 'SOLD', realized_gain_change_eur: '46', retained_gain_change_eur: '0' }], diagnostics: [] },
      '1Y': { state: 'unavailable', start: '2026-01-01T00:00:00Z', end: '2026-01-05T00:00:00Z', shorter_coverage: true, points: [], diagnostics: ['missing_observed_price:ETF'] } } } } });
  expect(target.textContent).toContain('EUR 47');
  expect(target.textContent).toContain('Estimated cash-flow-adjusted return: 10%');
  expect(target.textContent).toContain('Finalized percentage cutoff: 2026-01-05T00:00:00Z');
  expect(target.querySelector('svg')?.getAttribute('aria-label')).toContain('2026-01-01T00:00:00Z');
  expect(target.querySelector('svg')?.getAttribute('aria-label')).toContain('2026-01-05T00:00:00Z');
  expect(target.textContent).toContain('SOLD');
  const year = Array.from(target.querySelectorAll('button')).find(button => button.textContent === '1Y')!;
  year.click();
  expect(target.textContent).toContain('Shorter observed coverage');
  expect(target.textContent).toContain('missing_observed_price:ETF');
  expect(target.textContent).toContain('Estimated cash-flow-adjusted return unavailable');
  expect(target.textContent).not.toContain('10%');
  expect(target.querySelector('svg')).toBeNull();
});

test('missing history never creates a zero or demonstration chart', () => {
  const target = document.createElement('section');
  renderPerformance(target, { generation_id: 'g1', read_model: {} });
  expect(target.textContent).toContain('Observed history unavailable');
  expect(target.textContent).not.toContain('EUR 0');
  expect(target.querySelector('svg')).toBeNull();
});
