import { describe, it, expect } from 'vitest';
import { filterPortfolioHistory, getAssetPortfolioHistory } from './timeframe';
import { PortfolioDailyHistoryRecord } from '../types/portfolio';

describe('Timeframe Filter Logic', () => {
  const sampleHistory: PortfolioDailyHistoryRecord[] = [
    {
      date: '2025-01-15',
      total_equity_eur: 30000,
      invested_capital_eur: 28000,
      cash_balance_eur: 500,
      unrealized_pnl_eur: 2000,
      unrealized_pnl_pct: 7.14,
    },
    {
      date: '2025-06-01',
      total_equity_eur: 35000,
      invested_capital_eur: 32000,
      cash_balance_eur: 800,
      unrealized_pnl_eur: 3000,
      unrealized_pnl_pct: 9.38,
    },
    {
      date: '2025-10-15',
      total_equity_eur: 38000,
      invested_capital_eur: 35000,
      cash_balance_eur: 1000,
      unrealized_pnl_eur: 3000,
      unrealized_pnl_pct: 8.57,
    },
    {
      date: '2026-07-15',
      total_equity_eur: 44000,
      invested_capital_eur: 40000,
      cash_balance_eur: 1200,
      unrealized_pnl_eur: 4000,
      unrealized_pnl_pct: 10.0,
    },
    {
      date: '2026-09-15',
      total_equity_eur: 46000,
      invested_capital_eur: 41000,
      cash_balance_eur: 1300,
      unrealized_pnl_eur: 5000,
      unrealized_pnl_pct: 12.2,
    },
    {
      date: '2026-10-10',
      total_equity_eur: 47500,
      invested_capital_eur: 42000,
      cash_balance_eur: 1400,
      unrealized_pnl_eur: 5500,
      unrealized_pnl_pct: 13.1,
    },
    {
      date: '2026-10-19',
      total_equity_eur: 48250,
      invested_capital_eur: 42238,
      cash_balance_eur: 1420,
      unrealized_pnl_eur: 6012,
      unrealized_pnl_pct: 14.23,
    },
  ];

  const refDate = new Date('2026-10-19T12:00:00Z');

  it('returns all records sorted by date for ALL timeframe', () => {
    // Pass in reverse order to ensure sorting works
    const reversed = [...sampleHistory].reverse();
    const result = filterPortfolioHistory(reversed, 'ALL', refDate);

    expect(result.length).toBe(7);
    expect(result[0].date).toBe('2025-01-15');
    expect(result[result.length - 1].date).toBe('2026-10-19');
  });

  it('filters to the last 1 month for 1M timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '1M', refDate);
    // cutoff: 2026-09-19 -> includes 2026-10-10 and 2026-10-19
    expect(result.map((r) => r.date)).toEqual(['2026-10-10', '2026-10-19']);
  });

  it('filters to the last 3 months for 3M timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '3M', refDate);
    // cutoff: 2026-07-19 -> includes 2026-09-15, 2026-10-10, 2026-10-19
    expect(result.map((r) => r.date)).toEqual([
      '2026-09-15',
      '2026-10-10',
      '2026-10-19',
    ]);
  });

  it('filters to the last 1 year for 1Y timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '1Y', refDate);
    // cutoff: 2026-10-19 minus 1 year = 2025-10-19
    // includes 2026-07-15, 2026-09-15, 2026-10-10, 2026-10-19
    expect(result.map((r) => r.date)).toEqual([
      '2026-07-15',
      '2026-09-15',
      '2026-10-10',
      '2026-10-19',
    ]);
  });

  it('defaults to latest date in history when referenceDate is not provided', () => {
    const result = filterPortfolioHistory(sampleHistory, '1M');
    expect(result.map((r) => r.date)).toEqual(['2026-10-10', '2026-10-19']);
  });

  it('handles empty history gracefully', () => {
    const result = filterPortfolioHistory([], '1M');
    expect(result).toEqual([]);
  });

  it('returns all available points if history span is shorter than timeframe', () => {
    const shortHistory = sampleHistory.slice(-2);
    const result = filterPortfolioHistory(shortHistory, '1Y', refDate);
    expect(result.length).toBe(2);
  });

  it('filters to the last 1 week for 1W timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '1W', refDate);
    // cutoff: 2026-10-19 minus 7 days = 2026-10-12 -> includes 2026-10-19
    expect(result.map((r) => r.date)).toEqual(['2026-10-19']);
  });

  it('generates 24-hour hourly points for 24H timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '24H', refDate);
    expect(result.length).toBe(25);
    expect(result[result.length - 1].total_equity_eur).toBe(48250);
  });
});

describe('getAssetPortfolioHistory', () => {
  const historyWithBreakdown: PortfolioDailyHistoryRecord[] = [
    {
      date: '2025-01-01',
      total_equity_eur: 1000,
      invested_capital_eur: 1000,
      cash_balance_eur: 1000,
      unrealized_pnl_eur: 0,
      unrealized_pnl_pct: 0,
      asset_breakdown: {},
    },
    {
      date: '2025-02-01',
      total_equity_eur: 1200,
      invested_capital_eur: 1000,
      cash_balance_eur: 200,
      unrealized_pnl_eur: 200,
      unrealized_pnl_pct: 20,
      asset_breakdown: {
        'BTC-EUR': {
          value_eur: 1000,
          cost_eur: 800,
          shares: 0.05,
          price_eur: 20000,
          pnl_eur: 200,
          pnl_pct: 25,
        },
      },
    },
    {
      date: '2025-03-01',
      total_equity_eur: 1500,
      invested_capital_eur: 1000,
      cash_balance_eur: 200,
      unrealized_pnl_eur: 500,
      unrealized_pnl_pct: 50,
      asset_breakdown: {
        'BTC-EUR': {
          value_eur: 1300,
          cost_eur: 800,
          shares: 0.05,
          price_eur: 26000,
          pnl_eur: 500,
          pnl_pct: 62.5,
        },
      },
    },
  ];

  it('returns original history when assetKey is null or ALL', () => {
    expect(getAssetPortfolioHistory(historyWithBreakdown, null)).toEqual(historyWithBreakdown);
    expect(getAssetPortfolioHistory(historyWithBreakdown, 'ALL')).toEqual(historyWithBreakdown);
  });

  it('filters to individual asset valuation and trims leading empty dates', () => {
    const btcHistory = getAssetPortfolioHistory(historyWithBreakdown, 'BTC-EUR');
    // Leading date 2025-01-01 had 0 BTC, should be trimmed to start from 2025-02-01
    expect(btcHistory.length).toBe(2);
    expect(btcHistory[0].date).toBe('2025-02-01');
    expect(btcHistory[0].total_equity_eur).toBe(1000);
    expect(btcHistory[0].invested_capital_eur).toBe(800);
    expect(btcHistory[0].unrealized_pnl_eur).toBe(200);

    expect(btcHistory[1].date).toBe('2025-03-01');
    expect(btcHistory[1].total_equity_eur).toBe(1300);
    expect(btcHistory[1].unrealized_pnl_eur).toBe(500);
  });
});
