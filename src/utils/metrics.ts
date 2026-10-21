import {
  PortfolioDailyHistoryRecord,
  CurrentAssetHoldingRecord,
  PortfolioMetrics,
} from '../types/portfolio';

/**
 * Computes top-level portfolio summary metrics from history snapshots and current holdings.
 */
export function calculatePortfolioMetrics(
  history: PortfolioDailyHistoryRecord[],
  holdings: CurrentAssetHoldingRecord[],
  totalDividendsEur = 0
): PortfolioMetrics {
  const totalHoldingsCount = holdings.length;
  const dividends = Number(totalDividendsEur.toFixed(2));

  if (history && history.length > 0) {
    const sorted = [...history].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    const latest = sorted[sorted.length - 1];

    const totalPortfolioValue = latest.total_equity_eur;
    const netInvestedCapital = latest.invested_capital_eur;
    const totalGainLossEur = latest.unrealized_pnl_eur;
    const totalGainLossPct =
      netInvestedCapital > 0 ? (totalGainLossEur / netInvestedCapital) * 100 : 0;
    const freeCashBalance = latest.cash_balance_eur;

    return {
      totalPortfolioValue,
      netInvestedCapital,
      totalGainLossEur,
      totalGainLossPct,
      freeCashBalance,
      totalHoldingsCount,
      totalDividendsEur: dividends,
    };
  }

  // Fallback: If no history exists, aggregate from current asset holdings
  if (holdings && holdings.length > 0) {
    const totalPortfolioValue = holdings.reduce(
      (sum, h) => sum + (h.total_value_eur || 0),
      0
    );
    const netInvestedCapital = holdings.reduce(
      (sum, h) => sum + (h.total_cost_eur || 0),
      0
    );
    const totalGainLossEur = totalPortfolioValue - netInvestedCapital;
    const totalGainLossPct =
      netInvestedCapital > 0 ? (totalGainLossEur / netInvestedCapital) * 100 : 0;

    return {
      totalPortfolioValue,
      netInvestedCapital,
      totalGainLossEur,
      totalGainLossPct,
      freeCashBalance: 0,
      totalHoldingsCount,
      totalDividendsEur: dividends,
    };
  }

  return {
    totalPortfolioValue: 0,
    netInvestedCapital: 0,
    totalGainLossEur: 0,
    totalGainLossPct: 0,
    freeCashBalance: 0,
    totalHoldingsCount: 0,
    totalDividendsEur: dividends,
  };
}

/**
 * Formats a number as a EUR currency string, e.g. €48,250.75 or -€1,250.50
 */
export function formatEur(amount: number): string {
  const isNegative = amount < 0;
  const absVal = Math.abs(amount);
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absVal);

  return isNegative ? `-€${formatted}` : `€${formatted}`;
}

/**
 * Formats a percentage with optional leading '+' sign, e.g. +14.23% or -2.50%
 */
export function formatPct(percentage: number, includeSign = true): string {
  const formatted = Math.abs(percentage).toFixed(2);
  if (percentage > 0 && includeSign) {
    return `+${formatted}%`;
  }
  if (percentage < 0) {
    return `-${formatted}%`;
  }
  return `${formatted}%`;
}
