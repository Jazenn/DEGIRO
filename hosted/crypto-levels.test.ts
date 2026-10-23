import { expect, test } from 'vitest';
import { linearPercentile, suggestedLevels } from './crypto-levels';

const now = '2026-10-23T12:00:00Z';
function series() {
  const rows: Record<string, Record<string, string>> = {};
  // Oldest close 1, newest close365; the following midnight closes each day.
  for (let n = 1; n <= 365; n++) {
    const at = new Date(Date.parse('2025-10-23T00:00:00Z') + n * 86400000).toISOString();
    rows[at] = { price_eur: String(n), observed_at: at, provider: 'synthetic daily EUR',
      currency: 'EUR', adjustment_basis: 'unadjusted', retrieved_at: now };
  }
  return rows;
}

test('linear percentile uses independently hand-calculated adjacent observations', () => {
  expect(linearPercentile(['100', '20', '10', '40'], '35')).toBe('21');
  expect(linearPercentile(['10', '20', '40', '100'], '75')).toBe('55');
  expect(linearPercentile(['10', '20', '40', '100'], '95')).toBe('91');
});

test('complete public market data works without a personal ledger and excludes live intraday points', () => {
  const data = series();
  data['2026-10-23T10:00:00Z'] = { price_eur: '999999', observed_at: '2026-10-23T10:00:00Z' };
  const result = suggestedLevels('BTC-EUR', data, now);
  expect(result.state).toBe('ready');
  expect(result.window_start).toBe('2025-10-23');
  expect(result.window_end).toBe('2026-10-22');
  expect(result.purchase.map(row => row.price_eur)).toEqual(['128.4', '73.8', '37.4']);
  expect(result.sale.map(row => row.price_eur)).toEqual(['274', '328.6', '346.8']);
  expect(result.context).toHaveLength(90);
  expect(result.context[89].day).toBe('2026-10-22');
});

test('missing history and rolling expiry pause suggestions rather than shorten the window', () => {
  const data = series();
  delete data['2026-10-23T00:00:00.000Z'];
  const missing = suggestedLevels('BTC-EUR', data, now);
  expect(missing.state).toBe('paused');
  expect(missing.missing_days).toEqual(['2026-10-22']);
  expect(missing.purchase).toEqual([]);
  const expired = suggestedLevels('BTC-EUR', series(), '2026-10-24T12:00:00Z');
  expect(expired.state).toBe('paused');
  expect(expired.missing_days).toEqual(['2026-10-23']);
  const renewed = series();
  renewed['2026-10-24T00:00:00Z'] = { price_eur: '366', observed_at: '2026-10-24T00:00:00Z',
    provider: 'synthetic daily EUR', currency: 'EUR', adjustment_basis: 'unadjusted', retrieved_at: '2026-10-24T00:23:00Z' };
  expect(suggestedLevels('BTC-EUR', renewed, '2026-10-24T12:00:00Z').purchase[0].price_eur).toBe('129.4');
});

test('coincident or unordered levels require review and BTC ETH drafts stay independent', () => {
  const data = series();
  for (const quote of Object.values(data)) quote.price_eur = '100';
  expect(suggestedLevels('BTC-EUR', data, now).state).toBe('review');
  expect(suggestedLevels('BTC-EUR', series(), now, { purchase: ['10','20','35'], sale: ['75','90','95'] }).state).toBe('review');
  const edited = suggestedLevels('BTC-EUR', series(), now, { purchase: ['30','20','10'], sale: ['75','90','95'] });
  expect(edited.purchase[0].price_eur).toBe('110.2');
  expect(suggestedLevels('ETH-EUR', series(), now).purchase[0].price_eur).toBe('128.4');
});

test('unsupported currency, conflicting observations or inconsistent sources pause the window', () => {
  for (const changes of [{ currency: 'USD' }, { provider: 'another provider' }, { observed_at: '2026-10-23T01:00:00Z' }]) {
    const data = series();
    Object.assign(data['2026-10-23T00:00:00.000Z'], changes);
    expect(suggestedLevels('ETH-EUR', data, now).state).toBe('paused');
  }
});
