import { neon } from '@neondatabase/serverless';
import {
  PortfolioDailyHistoryRecord,
  CurrentAssetHoldingRecord,
  DashboardData,
  PortfolioAssetSetting,
} from '../types/portfolio';
import { IngestedTransaction } from '../utils/csvParser';
import { calculatePortfolioMetrics } from '../utils/metrics';

/**
 * Creates a Neon Serverless HTTP SQL client.
 */
export function createNeonClient(databaseUrl: string) {
  return neon(databaseUrl);
}

/**
 * Default asset configuration settings matching the DEGIRO portfolio specification.
 */
export function getDefaultAssetSettings(): PortfolioAssetSetting[] {
  return [
    {
      symbol: 'VWCE.DE',
      display_name: 'Vanguard FTSE All-World UCITS ETF',
      target_pct: 55.5,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'EXUS.DE',
      display_name: 'iShares MSCI World ex-USA UCITS ETF',
      target_pct: 21.0,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'BTC-EUR',
      display_name: 'Bitcoin',
      target_pct: 8.0,
      buy_dip_trigger: 58500,
      sell_profit_trigger: 75420,
      sell_profit_pct: 15.0,
      is_crypto: true,
      buy_budget: 350,
    },
    {
      symbol: 'IMAE.AS',
      display_name: 'iShares European Property Yield / Small ETF',
      target_pct: 8.5,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'ASWC.DE',
      display_name: 'Clean Energy & Technology ETF',
      target_pct: 5.0,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'ETH-EUR',
      display_name: 'Ethereum',
      target_pct: 2.0,
      buy_dip_trigger: 2800,
      sell_profit_trigger: 3800,
      sell_profit_pct: 15.0,
      is_crypto: true,
      buy_budget: 150,
    },
  ];
}

const LOCAL_STORAGE_SETTINGS_KEY = 'degiro_asset_settings';

export function loadLocalAssetSettings(): PortfolioAssetSetting[] | null {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LOCAL_STORAGE_SETTINGS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed;
    }
  } catch {
    // Ignore local storage parse error
  }
  return null;
}

export function saveLocalAssetSettings(settings: PortfolioAssetSetting[]): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(LOCAL_STORAGE_SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Ignore storage quota or access errors
  }
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

  const assetSettings = loadLocalAssetSettings() || getDefaultAssetSettings();

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
      target_pct: 5.0,
      drift_pct: 1.4,
      recommended_action_eur: 0.0,
    },
  ];

  // Sync holdings target_pct with assetSettings if available
  const syncedHoldings = holdings.map((h) => {
    const s = assetSettings.find(
      (item) => item.symbol === h.symbol || item.display_name === h.name
    );
    if (!s) return h;
    const target_pct = s.target_pct;
    const drift_pct = h.actual_pct - target_pct;
    return {
      ...h,
      target_pct,
      drift_pct,
    };
  });

  const metrics = calculatePortfolioMetrics(history, syncedHoldings);

  return {
    metrics,
    history,
    holdings: syncedHoldings,
    assetSettings,
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
  customSql?: (query: TemplateStringsArray, ...args: any[]) => Promise<any[]>
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

    // Query snapshot tables in parallel for sub-50ms read latency
    const [historyRows, holdingsRows, settingsRows] = await Promise.all([
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
      sql`
        SELECT 
          symbol,
          display_name,
          target_pct,
          buy_dip_trigger,
          sell_profit_trigger,
          sell_profit_pct,
          is_crypto,
          buy_budget,
          updated_at::text as updated_at
        FROM portfolio_asset_settings
        ORDER BY target_pct DESC
      `.catch(async () => {
        // Fallback to degiro_assets if portfolio_asset_settings doesn't exist yet
        return sql`
          SELECT 
            product_key as symbol,
            display_name,
            target_pct,
            t1_buy as buy_dip_trigger,
            t1_sell as sell_profit_trigger,
            15.0 as sell_profit_pct,
            (product_key ILIKE '%BTC%' OR product_key ILIKE '%ETH%' OR product_key ILIKE '%BITCOIN%' OR product_key ILIKE '%ETHEREUM%') as is_crypto,
            buy_budget,
            updated_at::text as updated_at
          FROM degiro_assets
          ORDER BY target_pct DESC
        `;
      }).catch(() => []),
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

    const assetSettings: PortfolioAssetSetting[] =
      settingsRows && settingsRows.length > 0
        ? settingsRows.map((r: any) => ({
            symbol: String(r.symbol),
            display_name: r.display_name ? String(r.display_name) : String(r.symbol),
            target_pct: Number(r.target_pct) || 0,
            buy_dip_trigger: r.buy_dip_trigger !== null && r.buy_dip_trigger !== undefined ? Number(r.buy_dip_trigger) : null,
            sell_profit_trigger: r.sell_profit_trigger !== null && r.sell_profit_trigger !== undefined ? Number(r.sell_profit_trigger) : null,
            sell_profit_pct: r.sell_profit_pct !== null && r.sell_profit_pct !== undefined ? Number(r.sell_profit_pct) : 15.0,
            is_crypto: Boolean(r.is_crypto),
            buy_budget: r.buy_budget !== null && r.buy_budget !== undefined ? Number(r.buy_budget) : null,
            updated_at: r.updated_at ? String(r.updated_at) : undefined,
          }))
        : getDefaultAssetSettings();

    const metrics = calculatePortfolioMetrics(history, holdings);

    return {
      metrics,
      history,
      holdings,
      assetSettings,
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

/**
 * Persists updated portfolio asset settings to the database and/or local cache.
 */
export async function saveAssetSettings(
  settings: PortfolioAssetSetting[],
  databaseUrl?: string,
  customSql?: (query: TemplateStringsArray, ...args: any[]) => Promise<any[]>
): Promise<boolean> {
  saveLocalAssetSettings(settings);

  const resolvedUrl =
    databaseUrl ||
    (typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.VITE_DATABASE_URL || import.meta.env.DATABASE_URL
      : undefined);

  if (!resolvedUrl && !customSql) {
    return true;
  }

  try {
    const sql = customSql || createNeonClient(resolvedUrl!);
    for (const setting of settings) {
      // Upsert into portfolio_asset_settings
      await sql`
        INSERT INTO portfolio_asset_settings (
          symbol, display_name, target_pct, buy_dip_trigger, sell_profit_trigger, sell_profit_pct, is_crypto, buy_budget, updated_at
        ) VALUES (
          ${setting.symbol}, ${setting.display_name}, ${setting.target_pct}, ${setting.buy_dip_trigger}, ${setting.sell_profit_trigger}, ${setting.sell_profit_pct ?? 15.0}, ${setting.is_crypto}, ${setting.buy_budget}, NOW()
        )
        ON CONFLICT (symbol) DO UPDATE SET
          display_name = EXCLUDED.display_name,
          target_pct = EXCLUDED.target_pct,
          buy_dip_trigger = EXCLUDED.buy_dip_trigger,
          sell_profit_trigger = EXCLUDED.sell_profit_trigger,
          sell_profit_pct = EXCLUDED.sell_profit_pct,
          is_crypto = EXCLUDED.is_crypto,
          buy_budget = EXCLUDED.buy_budget,
          updated_at = NOW()
      `;

      // Upsert into degiro_assets for backward compatibility
      await sql`
        INSERT INTO degiro_assets (
          product_key, display_name, target_pct, t1_buy, t1_sell, buy_budget, updated_at
        ) VALUES (
          ${setting.symbol}, ${setting.display_name}, ${setting.target_pct}, ${setting.buy_dip_trigger}, ${setting.sell_profit_trigger}, ${setting.buy_budget}, NOW()
        )
        ON CONFLICT (product_key) DO UPDATE SET
          display_name = EXCLUDED.display_name,
          target_pct = EXCLUDED.target_pct,
          t1_buy = EXCLUDED.t1_buy,
          t1_sell = EXCLUDED.t1_sell,
          buy_budget = EXCLUDED.buy_budget,
          updated_at = NOW()
      `;
    }
    return true;
  } catch (err) {
    console.warn('Failed to persist asset settings to database:', err);
    return false;
  }
}

const LOCAL_STORAGE_TRANSACTIONS_KEY = 'degiro_transactions_history';

export function loadLocalTransactions(): IngestedTransaction[] {
  if (typeof window === 'undefined' || !window.localStorage) {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(LOCAL_STORAGE_TRANSACTIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed;
    }
  } catch {
    // Ignore parse error
  }
  return [];
}

/**
 * Persists ingested transactions into degiro_transactions on Neon with
 * ON CONFLICT (row_hash) DO NOTHING. In demo mode or offline, stores to localStorage.
 */
export async function saveTransactions(
  transactions: IngestedTransaction[],
  databaseUrl?: string,
  customSql?: (query: TemplateStringsArray, ...args: any[]) => Promise<any[]>
): Promise<{ inserted: number; duplicates: number }> {
  if (!transactions || transactions.length === 0) {
    return { inserted: 0, duplicates: 0 };
  }

  // Local storage persistence
  const existingLocal = loadLocalTransactions();
  const existingHashes = new Set(existingLocal.map((t) => t.rowHash));
  let localInserted = 0;
  const combined = [...existingLocal];

  for (const tx of transactions) {
    if (!existingHashes.has(tx.rowHash)) {
      existingHashes.add(tx.rowHash);
      combined.push(tx);
      localInserted++;
    }
  }

  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      window.localStorage.setItem(
        LOCAL_STORAGE_TRANSACTIONS_KEY,
        JSON.stringify(combined)
      );
    } catch {
      // Ignore quota errors
    }
  }

  const resolvedUrl =
    databaseUrl ||
    (typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.VITE_DATABASE_URL || import.meta.env.DATABASE_URL
      : undefined);

  if (!resolvedUrl && !customSql) {
    return {
      inserted: localInserted,
      duplicates: transactions.length - localInserted,
    };
  }

  try {
    const sql = customSql || createNeonClient(resolvedUrl!);
    let dbInserted = 0;
    for (const tx of transactions) {
      const amountVal =
        tx.amount !== null && tx.amount !== undefined
          ? tx.amount
          : tx.value !== null && tx.value !== undefined
          ? tx.value
          : 0.0;
      const balanceVal =
        tx.balance !== null && tx.balance !== undefined ? tx.balance : 0.0;

      const res = await sql`
        INSERT INTO degiro_transactions (
          row_hash,
          date,
          time,
          product,
          isin,
          description,
          amount,
          balance,
          order_id
        ) VALUES (
          ${tx.rowHash},
          ${tx.date ? tx.date : null},
          ${tx.time ? tx.time : null},
          ${tx.product || null},
          ${tx.isin || null},
          ${tx.description || null},
          ${amountVal},
          ${balanceVal},
          ${tx.orderId || null}
        )
        ON CONFLICT (row_hash) DO NOTHING
      `;
      if (res && (res.length > 0 || (res as any).rowCount > 0)) {
        dbInserted++;
      }
    }
    return {
      inserted: dbInserted || localInserted,
      duplicates: transactions.length - (dbInserted || localInserted),
    };
  } catch (err) {
    console.warn('Failed to insert transactions into database:', err);
    return {
      inserted: localInserted,
      duplicates: transactions.length - localInserted,
    };
  }
}

/**
 * Updates in-memory DashboardData with new asset settings without requiring a page reload.
 * Recalculates holding targets and drift.
 */
export function applySettingsToDashboardData(
  data: DashboardData,
  settings: PortfolioAssetSetting[]
): DashboardData {
  const updatedHoldings = data.holdings.map((h) => {
    const s = settings.find(
      (item) => item.symbol === h.symbol || item.display_name === h.name
    );
    if (!s) return h;
    const target_pct = s.target_pct;
    const drift_pct = h.actual_pct - target_pct;
    return {
      ...h,
      target_pct,
      drift_pct,
    };
  });

  return {
    ...data,
    holdings: updatedHoldings,
    assetSettings: settings,
  };
}
