import { neon } from '@neondatabase/serverless';
import {
  PortfolioDailyHistoryRecord,
  CurrentAssetHoldingRecord,
  DashboardData,
} from '../types/portfolio';
import { calculatePortfolioMetrics } from '../utils/metrics';

/**
 * Creates a Neon Serverless HTTP SQL client.
 */
export function createNeonClient(databaseUrl: string) {
  return neon(databaseUrl);
}

/**
 * Generates realistic fallback demo data matching the Variant B FinTech specification.
 */
export function getDemoDashboardData(): DashboardData {
  const history: PortfolioDailyHistoryRecord[] = [
    {
      date: '2025-10-01',
      total_equity_eur: 36200.0,
      invested_capital_eur: 34000.0,
      cash_balance_eur: 1200.0,
      unrealized_pnl_eur: 2200.0,
      unrealized_pnl_pct: 6.47,
    },
    {
      date: '2025-11-01',
      total_equity_eur: 37500.0,
      invested_capital_eur: 34700.0,
      cash_balance_eur: 1150.0,
      unrealized_pnl_eur: 2800.0,
      unrealized_pnl_pct: 8.07,
    },
    {
      date: '2025-12-01',
      total_equity_eur: 39100.0,
      invested_capital_eur: 35400.0,
      cash_balance_eur: 1300.0,
      unrealized_pnl_eur: 3700.0,
      unrealized_pnl_pct: 10.45,
    },
    {
      date: '2026-01-01',
      total_equity_eur: 38400.0,
      invested_capital_eur: 36100.0,
      cash_balance_eur: 1050.0,
      unrealized_pnl_eur: 2300.0,
      unrealized_pnl_pct: 6.37,
    },
    {
      date: '2026-02-01',
      total_equity_eur: 40200.0,
      invested_capital_eur: 36800.0,
      cash_balance_eur: 1400.0,
      unrealized_pnl_eur: 3400.0,
      unrealized_pnl_pct: 9.24,
    },
    {
      date: '2026-03-01',
      total_equity_eur: 41800.0,
      invested_capital_eur: 37500.0,
      cash_balance_eur: 1250.0,
      unrealized_pnl_eur: 4300.0,
      unrealized_pnl_pct: 11.47,
    },
    {
      date: '2026-04-01',
      total_equity_eur: 43100.0,
      invested_capital_eur: 38200.0,
      cash_balance_eur: 1380.0,
      unrealized_pnl_eur: 4900.0,
      unrealized_pnl_pct: 12.83,
    },
    {
      date: '2026-05-01',
      total_equity_eur: 42900.0,
      invested_capital_eur: 38900.0,
      cash_balance_eur: 1100.0,
      unrealized_pnl_eur: 4000.0,
      unrealized_pnl_pct: 10.28,
    },
    {
      date: '2026-06-01',
      total_equity_eur: 44500.0,
      invested_capital_eur: 39600.0,
      cash_balance_eur: 1220.0,
      unrealized_pnl_eur: 4900.0,
      unrealized_pnl_pct: 12.37,
    },
    {
      date: '2026-07-01',
      total_equity_eur: 46100.0,
      invested_capital_eur: 40300.0,
      cash_balance_eur: 1350.0,
      unrealized_pnl_eur: 5800.0,
      unrealized_pnl_pct: 14.39,
    },
    {
      date: '2026-08-01',
      total_equity_eur: 45800.0,
      invested_capital_eur: 41000.0,
      cash_balance_eur: 1180.0,
      unrealized_pnl_eur: 4800.0,
      unrealized_pnl_pct: 11.71,
    },
    {
      date: '2026-09-01',
      total_equity_eur: 47300.0,
      invested_capital_eur: 41600.0,
      cash_balance_eur: 1290.0,
      unrealized_pnl_eur: 5700.0,
      unrealized_pnl_pct: 13.7,
    },
    {
      date: '2026-10-19',
      total_equity_eur: 48250.75,
      invested_capital_eur: 42238.45,
      cash_balance_eur: 1420.5,
      unrealized_pnl_eur: 6012.3,
      unrealized_pnl_pct: 14.23,
    },
  ];

  const holdings: CurrentAssetHoldingRecord[] = [
    {
      symbol: 'VWCE.DE',
      name: 'Vanguard FTSE All-World UCITS ETF',
      isin: 'IE00BK5BQT80',
      shares_held: 209.5,
      current_price_eur: 124.8,
      total_value_eur: 26145.6,
      total_cost_eur: 22890.0,
      unrealized_pnl_eur: 3255.6,
      actual_pct: 54.2,
      target_pct: 55.5,
      drift_pct: -1.3,
      recommended_action_eur: 625.0,
    },
    {
      symbol: 'EXUS.DE',
      name: 'iShares MSCI World ex-USA UCITS ETF',
      isin: 'IE0006WW1TQ4',
      shares_held: 185.0,
      current_price_eur: 56.1,
      total_value_eur: 10378.5,
      total_cost_eur: 9250.0,
      unrealized_pnl_eur: 1128.5,
      actual_pct: 21.5,
      target_pct: 21.0,
      drift_pct: 0.5,
      recommended_action_eur: 0.0,
    },
    {
      symbol: 'BTC-EUR',
      name: 'Bitcoin',
      isin: 'XFC000A2YY6Q',
      shares_held: 0.071,
      current_price_eur: 66500.0,
      total_value_eur: 4721.5,
      total_cost_eur: 3800.0,
      unrealized_pnl_eur: 921.5,
      actual_pct: 9.8,
      target_pct: 8.0,
      drift_pct: 1.8,
      recommended_action_eur: 0.0,
    },
    {
      symbol: 'IMAE.AS',
      name: 'iShares European Property Yield / Small ETF',
      isin: 'IE00B4K48X80',
      shares_held: 49.8,
      current_price_eur: 78.45,
      total_value_eur: 3906.81,
      total_cost_eur: 3600.0,
      unrealized_pnl_eur: 306.81,
      actual_pct: 8.1,
      target_pct: 8.5,
      drift_pct: -0.4,
      recommended_action_eur: 190.0,
    },
    {
      symbol: 'ASWC.DE',
      name: 'Clean Energy & Technology ETF',
      isin: 'IE000OJ5TQP4',
      shares_held: 120.0,
      current_price_eur: 25.8,
      total_value_eur: 3096.0,
      total_cost_eur: 2698.45,
      unrealized_pnl_eur: 397.55,
      actual_pct: 6.4,
      target_pct: 7.0,
      drift_pct: -0.6,
      recommended_action_eur: 75.0,
    },
  ];

  const metrics = calculatePortfolioMetrics(history, holdings);

  return {
    metrics,
    history,
    holdings,
    isDemo: true,
    lastUpdated: new Date().toISOString(),
  };
}

/**
 * Fetches dashboard snapshot data from Neon Serverless PostgreSQL.
 * Falls back to demo data gracefully if DATABASE_URL is not set or if the query fails.
 */
export async function fetchDashboardData(
  databaseUrl?: string,
  customSql?: (query: TemplateStringsArray) => Promise<any[]>
): Promise<DashboardData> {
  const resolvedUrl =
    databaseUrl ||
    (typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.VITE_DATABASE_URL || import.meta.env.DATABASE_URL
      : undefined);

  if (!resolvedUrl && !customSql) {
    return getDemoDashboardData();
  }

  try {
    const sql = customSql || createNeonClient(resolvedUrl!);

    // Query both snapshot tables in parallel for sub-50ms read latency
    const [historyRows, holdingsRows] = await Promise.all([
      sql`
        SELECT 
          date::text as date, 
          total_equity_eur, 
          invested_capital_eur, 
          cash_balance_eur, 
          unrealized_pnl_eur, 
          unrealized_pnl_pct 
        FROM portfolio_daily_history 
        ORDER BY date ASC
      `,
      sql`
        SELECT 
          symbol, 
          name, 
          isin, 
          shares_held, 
          current_price_eur, 
          total_value_eur, 
          total_cost_eur, 
          unrealized_pnl_eur, 
          actual_pct, 
          target_pct, 
          drift_pct, 
          recommended_action_eur 
        FROM current_asset_holdings 
        ORDER BY total_value_eur DESC
      `,
    ]);

    if (!historyRows || historyRows.length === 0) {
      console.warn('Neon database snapshot tables are empty, using demo fallback.');
      return getDemoDashboardData();
    }

    const history: PortfolioDailyHistoryRecord[] = historyRows.map((r: any) => ({
      date: typeof r.date === 'string' ? r.date.slice(0, 10) : new Date(r.date).toISOString().slice(0, 10),
      total_equity_eur: Number(r.total_equity_eur) || 0,
      invested_capital_eur: Number(r.invested_capital_eur) || 0,
      cash_balance_eur: Number(r.cash_balance_eur) || 0,
      unrealized_pnl_eur: Number(r.unrealized_pnl_eur) || 0,
      unrealized_pnl_pct: Number(r.unrealized_pnl_pct) || 0,
    }));

    const holdings: CurrentAssetHoldingRecord[] = (holdingsRows || []).map((r: any) => ({
      symbol: String(r.symbol),
      name: String(r.name),
      isin: r.isin ? String(r.isin) : null,
      shares_held: Number(r.shares_held) || 0,
      current_price_eur: Number(r.current_price_eur) || 0,
      total_value_eur: Number(r.total_value_eur) || 0,
      total_cost_eur: Number(r.total_cost_eur) || 0,
      unrealized_pnl_eur: Number(r.unrealized_pnl_eur) || 0,
      actual_pct: Number(r.actual_pct) || 0,
      target_pct: Number(r.target_pct) || 0,
      drift_pct: Number(r.drift_pct) || 0,
      recommended_action_eur: Number(r.recommended_action_eur) || 0,
    }));

    const metrics = calculatePortfolioMetrics(history, holdings);

    return {
      metrics,
      history,
      holdings,
      isDemo: false,
      lastUpdated: new Date().toISOString(),
    };
  } catch (err) {
    console.warn(
      'Neon database query failed, gracefully displaying demo dashboard data:',
      err
    );
    return getDemoDashboardData();
  }
}
