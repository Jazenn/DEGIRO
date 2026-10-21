import { describe, it, expect } from 'vitest';
import {
  calculatePortfolioMetrics,
  formatEur,
  formatPct,
} from './metrics';
import {
  PortfolioDailyHistoryRecord,
  CurrentAssetHoldingRecord,
} from '../types/portfolio';

describe('Portfolio Metrics Calculation', () => {
  const sampleHistory: PortfolioDailyHistoryRecord[] = [
    {
      date: '2026-09-01',
      total_equity_eur: 45000.0,
      invested_capital_eur: 40000.0,
      cash_balance_eur: 1000.0,
      unrealized_pnl_eur: 5000.0,
      unrealized_pnl_pct: 12.5,
    },
    {
      date: '2026-10-19',
      total_equity_eur: 48250.75,
      invested_capital_eur: 42238.45,
      cash_balance_eur: 1420.5,
      unrealized_pnl_eur: 6012.3,
      unrealized_pnl_pct: 14.234,
    },
  ];

  const sampleHoldings: CurrentAssetHoldingRecord[] = [
    {
      symbol: 'VWCE.DE',
      name: 'Vanguard FTSE All-World',
      isin: 'IE00BK5BQT80',
      shares_held: 200,
      current_price_eur: 124.8,
      total_value_eur: 24960.0,
      total_cost_eur: 21000.0,
      unrealized_pnl_eur: 3960.0,
      actual_pct: 54.2,
      target_pct: 55.5,
      drift_pct: -1.3,
      recommended_action_eur: 625.0,
    },
    {
      symbol: 'BTC-EUR',
      name: 'Bitcoin',
      isin: null,
      shares_held: 0.05,
      current_price_eur: 65000.0,
      total_value_eur: 3250.0,
      total_cost_eur: 2500.0,
      unrealized_pnl_eur: 750.0,
      actual_pct: 7.0,
      target_pct: 8.0,
      drift_pct: -1.0,
      recommended_action_eur: 460.0,
    },
  ];

  it('computes metrics from the latest history snapshot', () => {
    const metrics = calculatePortfolioMetrics(sampleHistory, sampleHoldings);

    expect(metrics.totalPortfolioValue).toBe(48250.75);
    expect(metrics.netInvestedCapital).toBe(42238.45);
    expect(metrics.totalGainLossEur).toBeCloseTo(6012.3, 2);
    expect(metrics.totalGainLossPct).toBeCloseTo(14.234, 3);
    expect(metrics.freeCashBalance).toBe(1420.5);
    expect(metrics.totalHoldingsCount).toBe(2);
  });

  it('handles empty history gracefully using holdings fallback', () => {
    const metrics = calculatePortfolioMetrics([], sampleHoldings);

    expect(metrics.totalPortfolioValue).toBe(28210.0);
    expect(metrics.netInvestedCapital).toBe(23500.0);
    expect(metrics.totalGainLossEur).toBe(4710.0);
    expect(metrics.totalGainLossPct).toBeCloseTo(20.04, 2);
    expect(metrics.freeCashBalance).toBe(0);
    expect(metrics.totalHoldingsCount).toBe(2);
  });

  it('handles empty history and empty holdings without throwing or NaN', () => {
    const metrics = calculatePortfolioMetrics([], []);

    expect(metrics.totalPortfolioValue).toBe(0);
    expect(metrics.netInvestedCapital).toBe(0);
    expect(metrics.totalGainLossEur).toBe(0);
    expect(metrics.totalGainLossPct).toBe(0);
    expect(metrics.freeCashBalance).toBe(0);
    expect(metrics.totalHoldingsCount).toBe(0);
  });

  it('avoids NaN / Infinity when invested capital is zero', () => {
    const zeroCapitalHistory: PortfolioDailyHistoryRecord[] = [
      {
        date: '2026-10-19',
        total_equity_eur: 500.0,
        invested_capital_eur: 0.0,
        cash_balance_eur: 500.0,
        unrealized_pnl_eur: 500.0,
        unrealized_pnl_pct: 0.0,
      },
    ];

    const metrics = calculatePortfolioMetrics(zeroCapitalHistory, []);
    expect(metrics.totalGainLossPct).toBe(0);
  });

  it('includes total dividends paid out when provided', () => {
    const metrics = calculatePortfolioMetrics(sampleHistory, sampleHoldings, 384.5);
    expect(metrics.totalDividendsEur).toBe(384.5);
  });

  it('defaults total dividends to 0 when not provided', () => {
    const metrics = calculatePortfolioMetrics(sampleHistory, sampleHoldings);
    expect(metrics.totalDividendsEur).toBe(0);
  });
});

describe('Formatting Utilities', () => {
  it('formats positive EUR amounts with currency symbol and thousands separators', () => {
    expect(formatEur(48250.75)).toBe('€48,250.75');
  });

  it('formats negative EUR amounts clearly', () => {
    expect(formatEur(-1250.5)).toBe('-€1,250.50');
  });

  it('formats zero EUR', () => {
    expect(formatEur(0)).toBe('€0.00');
  });

  it('formats positive percentages with leading plus sign', () => {
    expect(formatPct(14.234)).toBe('+14.23%');
  });

  it('formats negative percentages with minus sign', () => {
    expect(formatPct(-2.5)).toBe('-2.50%');
  });

  it('formats zero percentage without plus sign', () => {
    expect(formatPct(0)).toBe('0.00%');
  });
});
