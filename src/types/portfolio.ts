export interface PortfolioDailyHistoryRecord {
  date: string;
  total_equity_eur: number;
  invested_capital_eur: number;
  cash_balance_eur: number;
  unrealized_pnl_eur: number;
  unrealized_pnl_pct: number;
}

export interface CurrentAssetHoldingRecord {
  symbol: string;
  name: string;
  isin: string | null;
  shares_held: number;
  current_price_eur: number;
  total_value_eur: number;
  total_cost_eur: number;
  unrealized_pnl_eur: number;
  actual_pct: number;
  target_pct: number;
  drift_pct: number;
  recommended_action_eur: number;
}

export interface PortfolioMetrics {
  totalPortfolioValue: number;
  netInvestedCapital: number;
  totalGainLossEur: number;
  totalGainLossPct: number;
  freeCashBalance: number;
  totalHoldingsCount: number;
}

export type Timeframe = '1M' | '3M' | '1Y' | 'ALL';

export interface DashboardData {
  metrics: PortfolioMetrics;
  history: PortfolioDailyHistoryRecord[];
  holdings: CurrentAssetHoldingRecord[];
  isDemo: boolean;
  lastUpdated: string | null;
}
