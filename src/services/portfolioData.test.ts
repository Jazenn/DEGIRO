import { describe, it, expect, vi } from 'vitest';
import {
  fetchDashboardData,
  getDemoDashboardData,
} from './portfolioData';

describe('Neon Data Query Adapter', () => {
  it('returns demo dashboard data with isDemo: true when no database URL is set', async () => {
    const data = await fetchDashboardData(undefined);

    expect(data.isDemo).toBe(true);
    expect(data.metrics.totalPortfolioValue).toBeGreaterThan(0);
    expect(data.metrics.netInvestedCapital).toBeGreaterThan(0);
    expect(data.metrics.freeCashBalance).toBeGreaterThan(0);
    expect(data.history.length).toBeGreaterThan(0);
    expect(data.holdings.length).toBeGreaterThan(0);
    expect(data.lastUpdated).toBeTruthy();
  });

  it('provides realistic demo data matching Variant B prototype specifications', () => {
    const demo = getDemoDashboardData();

    expect(demo.metrics.totalPortfolioValue).toBeCloseTo(48250.75, 1);
    expect(demo.metrics.netInvestedCapital).toBeCloseTo(42238.45, 1);
    expect(demo.metrics.freeCashBalance).toBeCloseTo(1420.5, 1);
    expect(demo.metrics.totalGainLossEur).toBeCloseTo(6012.3, 1);
    expect(demo.metrics.totalGainLossPct).toBeCloseTo(14.23, 1);
    expect(demo.holdings.some((h) => h.symbol === 'VWCE.DE')).toBe(true);
  });

  it('executes parallel queries against Neon and maps rows when client succeeds', async () => {
    const mockSql = vi.fn().mockImplementation(async (queryStrings: TemplateStringsArray) => {
      const query = queryStrings.join('');
      if (query.includes('portfolio_daily_history')) {
        return [
          {
            date: '2026-10-18',
            total_equity_eur: '47900.00',
            invested_capital_eur: '42238.45',
            cash_balance_eur: '1420.50',
            unrealized_pnl_eur: '5661.55',
            unrealized_pnl_pct: '13.40',
          },
          {
            date: '2026-10-19',
            total_equity_eur: '48250.75',
            invested_capital_eur: '42238.45',
            cash_balance_eur: '1420.50',
            unrealized_pnl_eur: '6012.30',
            unrealized_pnl_pct: '14.23',
          },
        ];
      }
      if (query.includes('current_asset_holdings')) {
        return [
          {
            symbol: 'VWCE.DE',
            name: 'Vanguard FTSE All-World',
            isin: 'IE00BK5BQT80',
            shares_held: '200',
            current_price_eur: '124.80',
            total_value_eur: '24960.00',
            total_cost_eur: '21000.00',
            unrealized_pnl_eur: '3960.00',
            actual_pct: '51.73',
            target_pct: '55.50',
            drift_pct: '-3.77',
            recommended_action_eur: '625.00',
          },
        ];
      }
      return [];
    });

    const data = await fetchDashboardData('postgres://fake:secret@ep-cool.neon.tech/neondb', mockSql as any);

    expect(data.isDemo).toBe(false);
    expect(data.history.length).toBe(2);
    expect(data.history[1].total_equity_eur).toBe(48250.75);
    expect(data.holdings.length).toBe(1);
    expect(data.holdings[0].symbol).toBe('VWCE.DE');
    expect(data.metrics.totalPortfolioValue).toBe(48250.75);
  });

  it('falls back gracefully to demo data if the Neon query fails', async () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const failingSql = vi.fn().mockRejectedValue(new Error('Connection timeout to Neon'));

    const data = await fetchDashboardData('postgres://fake:secret@ep-cool.neon.tech/neondb', failingSql as any);

    expect(data.isDemo).toBe(true);
    expect(data.history.length).toBeGreaterThan(0);
    expect(consoleWarnSpy).toHaveBeenCalled();
    consoleWarnSpy.mockRestore();
  });
});
