// @vitest-environment jsdom
import { expect, test } from 'vitest';
// @ts-expect-error browser module
import { renderExposure } from './public/exposure.js';

test('dated partial exposure displays covered fractions and unknown overlap without exact diversification claims', () => {
  document.body.innerHTML = '<section id="exposure"></section>';
  renderExposure(document.querySelector('section'), {
    generation_id: 'synthetic-generation', read_model: { etf_exposure: {
      schema_version: 'etf-exposure-v1', covered_portfolio_fraction: '0.30',
      countries: { US: '30' }, sectors: { Technology: '30' }, limitations: ['Unreported fractions remain unknown.'],
      funds: [{ fund_id: 'SYNTHETIC-A', state: 'partial', provider: 'Synthetic provider',
        as_of: '2026-09-30', retrieved_at: '2026-10-23T10:00:00Z', source_url: 'https://provider.example/fund',
        covered_fund_fraction: '0.5', covered_reported_fraction: '0.5', weight_basis: 'fund_net_assets',
        top_ten_weight_pct: '50', concentration_basis: 'observed_lower_bound',
        countries: { US: '50' }, sectors: { Technology: '50' }, limitations: ['Partial holdings.'],
        holdings: [{ name: '<img src=x onerror=alert(1)>', weight_pct: '50', country: 'US', sector: 'Technology' }] },
        { fund_id: 'SYNTHETIC-B', state: 'unavailable', limitations: ['No dated source.'] }],
      overlap: [{ fund_a: 'SYNTHETIC-A', fund_b: 'SYNTHETIC-B', state: 'unavailable', observed_overlap_pct: null, reason: 'Dates or identifiers incompatible.' }],
    } },
  });
  expect(document.body.textContent).toContain('30% of invested asset value');
  expect(document.body.textContent).toContain('2026-09-30');
  expect(document.body.textContent).toContain('50% of fund net assets');
  expect(document.body.textContent).toContain('observed lower bound');
  expect(document.body.textContent).toContain('Overlap unavailable');
  expect(document.querySelector('img')).toBeNull();
  expect(document.querySelector('section')?.getAttribute('data-generation')).toBe('synthetic-generation');
});

test('absent exposure is visibly unavailable, never invented from asset names', () => {
  document.body.innerHTML = '<section></section>';
  renderExposure(document.querySelector('section'), { generation_id: 'no-data', read_model: {} });
  expect(document.body.textContent).toContain('No dated ETF holdings have been published');
  expect(document.body.textContent).not.toContain('0%');
});

test('complete dated compatible fixture distinguishes covered fund weights from investment predictions', () => {
  document.body.innerHTML = '<section></section>';
  renderExposure(document.querySelector('section'), { generation_id: 'synthetic-complete', read_model: {
    etf_exposure: { schema_version: 'etf-exposure-v1', covered_portfolio_fraction: '1',
      countries: { US: '100' }, sectors: { Technology: '100' }, limitations: [],
      funds: [{ fund_id: 'SYNTHETIC', state: 'covered', provider: 'Synthetic', source_url: 'https://provider.example',
        as_of: '2026-09-30', retrieved_at: '2026-10-23T10:00:00Z', covered_fund_fraction: '1',
        weight_basis: 'fund_net_assets', concentration_basis: 'exact', top_ten_weight_pct: '100', holdings: [], limitations: [] },
        { fund_id: 'SYNTHETIC-B', state: 'covered', provider: 'Synthetic', source_url: 'https://provider.example/b',
          as_of: '2026-09-30', retrieved_at: '2026-10-23T10:00:00Z', covered_fund_fraction: '1',
          weight_basis: 'fund_net_assets', concentration_basis: 'exact', top_ten_weight_pct: '100', holdings: [], limitations: [] }],
      overlap: [{ fund_a: 'SYNTHETIC', fund_b: 'SYNTHETIC-B', state: 'complete', as_of: '2026-09-30', observed_overlap_pct: '25', reason: 'Matching stable identifiers and dates.' }],
    },
  } });
  expect(document.body.textContent).toContain('100% of fund net assets covered');
  expect(document.body.textContent).toContain('25% overlap of fund weights');
  expect(document.body.textContent).toContain('Comparison as of 2026-09-30');
  expect(document.body.textContent).toContain('SYNTHETIC: 100% of fund net assets covered');
  expect(document.body.textContent).toContain('not a forecast');
});

test('revaluation withholds previous portfolio coverage while retaining dated fund facts', () => {
  document.body.innerHTML = '<section></section>';
  renderExposure(document.querySelector('section'), { generation_id: 'refreshed', read_model: {
    cutoff: '2026-10-23T11:00:00Z', ledger_version: 'ledger-1', etf_exposure: {
      schema_version: 'etf-exposure-v1', valuation_cutoff: '2026-10-23T10:00:00Z', ledger_version: 'ledger-1',
      covered_portfolio_fraction: '0.30', countries: { US: '30' }, sectors: { Technology: '30' }, limitations: [],
      funds: [], overlap: [],
    },
  } });
  expect(document.body.textContent).toContain('need recalculation for this valuation');
  expect(document.body.textContent).not.toContain('30%');
});
