import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchDashboardData,
  getDemoDashboardData,
} from './portfolioData';

describe('Neon Data Query Adapter', () => {
  beforeEach(() => {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.clear();
    }
  });
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

  it('provides default asset settings with crypto price triggers', () => {
    const demo = getDemoDashboardData();
    expect(demo.assetSettings).toBeDefined();
    expect(demo.assetSettings!.length).toBeGreaterThan(0);

    const btcSetting = demo.assetSettings!.find((s) => s.symbol === 'BTC-EUR');
    expect(btcSetting).toBeDefined();
    expect(btcSetting!.is_crypto).toBe(true);
    expect(btcSetting!.buy_dip_trigger).toBe(58500);
    expect(btcSetting!.sell_profit_trigger).toBe(75420);
    expect(btcSetting!.buy_budget).toBe(350);
  });

  it('persists asset settings via SQL upsert when Neon client is provided', async () => {
    const mockSql = vi.fn().mockImplementation(async () => []);

    const updatedSettings = [
      {
        symbol: 'VWCE.DE',
        display_name: 'Vanguard FTSE All-World',
        target_pct: 60.0,
        buy_dip_trigger: null,
        sell_profit_trigger: null,
        is_crypto: false,
        buy_budget: null,
      },
      {
        symbol: 'BTC-EUR',
        display_name: 'Bitcoin',
        target_pct: 10.0,
        buy_dip_trigger: 60000,
        sell_profit_trigger: 80000,
        is_crypto: true,
        buy_budget: 500,
      },
    ];

    const { saveAssetSettings } = await import('./portfolioData');
    const success = await saveAssetSettings(
      updatedSettings,
      'postgres://fake:secret@ep-cool.neon.tech/neondb',
      mockSql as any
    );

    expect(success).toBe(true);
    expect(mockSql).toHaveBeenCalled();
    const calls = mockSql.mock.calls.map((c) => c[0].join(''));
    expect(calls.some((sql) => sql.includes('portfolio_asset_settings') || sql.includes('degiro_assets'))).toBe(true);
  });

  it('applies updated settings to dashboard data in-memory and recalculates drift', async () => {
    const { applySettingsToDashboardData } = await import('./portfolioData');
    const demo = getDemoDashboardData();

    const originalVwce = demo.holdings.find((h) => h.symbol === 'VWCE.DE')!;
    expect(originalVwce.target_pct).toBe(55.5);

    const newSettings = demo.assetSettings!.map((s) =>
      s.symbol === 'VWCE.DE' ? { ...s, target_pct: 60.0 } : s
    );

    const updated = applySettingsToDashboardData(demo, newSettings);

    const updatedVwce = updated.holdings.find((h) => h.symbol === 'VWCE.DE')!;
    expect(updatedVwce.target_pct).toBe(60.0);
    expect(updatedVwce.drift_pct).toBeCloseTo(updatedVwce.actual_pct - 60.0, 2);
    expect(updated.assetSettings?.find((s) => s.symbol === 'VWCE.DE')?.target_pct).toBe(60.0);
  });

  it('persists transactions into localStorage in demo mode and skips duplicate hashes', async () => {
    const { saveTransactions, loadLocalTransactions } = await import('./portfolioData');

    const txs = [
      {
        date: '2026-01-15',
        time: '10:30',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 10 @ 120.50',
        quantity: 10,
        price: 120.5,
        value: -1205.0,
        amount: -1205.0,
        balance: 500.0,
        orderId: 'ORD-001',
        rowHash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90',
      },
    ];

    const res1 = await saveTransactions(txs);
    expect(res1.inserted).toBe(1);
    expect(res1.duplicates).toBe(0);

    const stored = loadLocalTransactions();
    expect(stored.length).toBe(1);
    expect(stored[0].rowHash).toBe('a1b2c3d4e5f60718293a4b5c6d7e8f90');

    // Attempting to re-save identical transaction should be counted as duplicate
    const res2 = await saveTransactions(txs);
    expect(res2.inserted).toBe(0);
    expect(res2.duplicates).toBe(1);
  });

  it('executes ON CONFLICT (row_hash) DO NOTHING queries against Neon when databaseUrl is provided', async () => {
    const { saveTransactions } = await import('./portfolioData');
    const mockSql = vi.fn().mockImplementation(async () => [{ count: 1 }]);

    const txs = [
      {
        date: '2026-01-20',
        time: '14:15',
        product: 'iShares MSCI World ex-USA',
        isin: 'IE0006WW1TQ4',
        description: 'Koop 5 @ 55.00',
        quantity: 5,
        price: 55.0,
        value: -275.0,
        amount: -275.0,
        balance: 225.0,
        orderId: 'ORD-002',
        rowHash: 'f1e2d3c4b5a60718293a4b5c6d7e8f99',
      },
    ];

    const result = await saveTransactions(
      txs,
      'postgres://fake:secret@ep-cool.neon.tech/neondb',
      mockSql as any
    );

    expect(mockSql).toHaveBeenCalled();
    const sqlText = mockSql.mock.calls[0][0].join('');
    expect(sqlText).toContain('INSERT INTO degiro_transactions');
    expect(sqlText).toContain('ON CONFLICT (row_hash) DO NOTHING');
    expect(result.inserted).toBe(1);
  });
});

