export interface AssetDaySnapshot {
  value_eur: number;
  cost_eur: number;
  shares: number;
  price_eur: number;
  pnl_eur: number;
  pnl_pct: number;
}

export interface PortfolioDailyHistoryRecord {
  date: string;
  total_equity_eur: number;
  invested_capital_eur: number;
  cash_balance_eur: number;
  unrealized_pnl_eur: number;
  unrealized_pnl_pct: number;
  asset_breakdown?: Record<string, AssetDaySnapshot>;
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

export type Timeframe = '24H' | '1W' | '1M' | '3M' | '1Y' | 'ALL';

export interface PortfolioAssetSetting {
  symbol: string;
  display_name: string;
  isin?: string | null;
  target_pct: number;
  buy_dip_trigger: number | null;
  sell_profit_trigger: number | null;
  sell_profit_pct?: number;
  is_crypto: boolean;
  buy_budget: number | null;
  updated_at?: string;
}

export interface DashboardData {
  metrics: PortfolioMetrics;
  history: PortfolioDailyHistoryRecord[];
  holdings: CurrentAssetHoldingRecord[];
  assetSettings?: PortfolioAssetSetting[];
  isDemo: boolean;
  lastUpdated: string | null;
}
