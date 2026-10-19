import { describe, it, expect } from 'vitest';
import { filterPortfolioHistory } from './timeframe';
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
});
