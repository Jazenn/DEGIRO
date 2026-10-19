import {
  CurrentAssetHoldingRecord,
  DashboardData,
  PortfolioAssetSetting,
  PortfolioDailyHistoryRecord,
} from '../types/portfolio';
import { IngestedTransaction } from './csvParser';
import { calculatePortfolioMetrics } from './metrics';
import { calculateDepositPlan } from './rebalance';

/**
 * Normalizes string values for fuzzy matching.
 */
function normalizeString(val: string | null | undefined): string {
  return (val || '').toLowerCase().trim();
}

/**
 * Checks if a transaction is an internal cash account or non-position record.
 */
function isInternalCashTransaction(tx: IngestedTransaction): boolean {
  const isin = normalizeString(tx.isin);
  const prod = normalizeString(tx.product);
  return (
    isin.includes('nlflatexacnt') ||
    isin.includes('flatex') ||
    prod.includes('aegon') ||
    prod.includes('degiro cash') ||
    prod === 'degiro' ||
    prod === 'flatex'
  );
}

/**
 * Checks if a transaction is a deposit or cash inflow.
 */
function isDepositTransaction(tx: IngestedTransaction): boolean {
  const desc = normalizeString(tx.description);
  const prod = normalizeString(tx.product);
  return (
    desc.includes('storting') ||
    desc.includes('ideal') ||
    desc.includes('deposit') ||
    prod.includes('storting') ||
    (isInternalCashTransaction(tx) && (tx.amount || 0) > 0)
  );
}

/**
 * Checks if a transaction is a withdrawal or cash outflow.
 */
function isWithdrawalTransaction(tx: IngestedTransaction): boolean {
  const desc = normalizeString(tx.description);
  const prod = normalizeString(tx.product);
  return (
    desc.includes('terugstorting') ||
    desc.includes('onttrekking') ||
    desc.includes('withdrawal') ||
    prod.includes('terugstorting') ||
    (isInternalCashTransaction(tx) && (tx.amount || 0) < 0)
  );
}

/**
 * Dynamically calculates full dashboard metrics, holdings, and portfolio history
 * directly from ingested DEGIRO transactions.
 */
export function calculateDashboardFromTransactions(
  transactions: IngestedTransaction[],
  assetSettings: PortfolioAssetSetting[] = []
): DashboardData | null {
  if (!transactions || transactions.length === 0) {
    return null;
  }

  // 1. Sort transactions chronologically
  const sorted = [...transactions].sort((a, b) => {
    const dateComp = (a.date || '').localeCompare(b.date || '');
    if (dateComp !== 0) return dateComp;
    return (a.time || '').localeCompare(b.time || '');
  });

  // 2. Compute Cash Balance
  // Check in reverse chronological order for the latest non-null balance (e.g. from Account.csv Saldo)
  let latestCashBalance: number | null = null;
  for (let i = sorted.length - 1; i >= 0; i--) {
    const tx = sorted[i];
    if (tx.balance !== null && tx.balance !== undefined && !isNaN(tx.balance)) {
      latestCashBalance = Number(tx.balance);
      break;
    }
  }

  // If no Saldo was present in CSV (e.g. Transactions.csv export), compute cash from flows
  if (latestCashBalance === null) {
    let computedCash = 0;
    for (const tx of sorted) {
      if (tx.amount !== null && !isNaN(tx.amount)) {
        computedCash += tx.amount;
      } else if (tx.value !== null && !isNaN(tx.value)) {
        computedCash += tx.value;
      }
    }
    latestCashBalance = computedCash;
  }

  // 3. Compute Net Invested Capital
  let totalDeposits = 0;
  let totalWithdrawals = 0;
  for (const tx of sorted) {
    if (isDepositTransaction(tx)) {
      const amt = Math.abs(tx.amount || tx.value || 0);
      totalDeposits += amt;
    } else if (isWithdrawalTransaction(tx)) {
      const amt = Math.abs(tx.amount || tx.value || 0);
      totalWithdrawals += amt;
    }
  }

  // 4. Compute Holdings per Asset
  const assetGroups = new Map<
    string,
    {
      symbol: string;
      name: string;
      isin: string | null;
      shares: number;
      totalCost: number;
      latestPrice: number;
    }
  >();

  for (const tx of sorted) {
    // Skip pure cash transactions and internal account rows
    if (isInternalCashTransaction(tx)) continue;
    if (!tx.product && !tx.isin) continue;
    if (isDepositTransaction(tx) || isWithdrawalTransaction(tx)) continue;

    const key = (tx.isin || tx.product || 'UNKNOWN').trim().toUpperCase();
    if (!assetGroups.has(key)) {
      assetGroups.set(key, {
        symbol: tx.isin || tx.product || 'UNKNOWN',
        name: tx.product || tx.isin || 'Asset',
        isin: tx.isin || null,
        shares: 0,
        totalCost: 0,
        latestPrice: Math.abs(tx.price || 0),
      });
    }

    const group = assetGroups.get(key)!;
    if (tx.price && tx.price > 0) {
      group.latestPrice = tx.price;
    }

    const rawQty = tx.quantity !== null ? Number(tx.quantity) : 0;
    const desc = normalizeString(tx.description);
    const isSell = desc.includes('verkoop') || desc.includes('sell') || rawQty < 0;
    const absQty = Math.abs(rawQty);

    if (absQty > 0) {
      if (isSell) {
        // Reduce shares and cost proportionally
        const fraction = group.shares > 0 ? Math.min(absQty / group.shares, 1.0) : 1.0;
        group.totalCost -= group.totalCost * fraction;
        group.shares = Math.max(0, group.shares - absQty);
      } else {
        // Buy
        group.shares += absQty;
        const buyCost = Math.abs(tx.amount || tx.value || absQty * (tx.price || group.latestPrice));
        group.totalCost += buyCost;
      }
    }
  }

  // Filter out closed positions (shares == 0)
  const activeHoldingsList: CurrentAssetHoldingRecord[] = [];
  let totalHoldingsValue = 0;
  let totalActiveCost = 0;

  for (const group of assetGroups.values()) {
    if (group.shares > 0.0001) {
      const price = group.latestPrice > 0 ? group.latestPrice : group.totalCost / group.shares;
      const totalValue = group.shares * price;
      totalHoldingsValue += totalValue;
      totalActiveCost += group.totalCost;

      // Find matching asset setting by symbol, isin, or name
      const setting = assetSettings.find((s) => {
        const sSym = normalizeString(s.symbol);
        const sName = normalizeString(s.display_name);
        const gKey = normalizeString(group.symbol);
        const gIsin = normalizeString(group.isin);
        const gName = normalizeString(group.name);
        return (
          sSym === gKey ||
          sSym === gIsin ||
          sName === gName ||
          gName.includes(sName) ||
          sName.includes(gName)
        );
      });

      const targetPct = setting ? setting.target_pct : 0;

      activeHoldingsList.push({
        symbol: setting ? setting.symbol : group.symbol,
        name: setting ? setting.display_name : group.name,
        isin: group.isin,
        shares_held: Number(group.shares.toFixed(4)),
        current_price_eur: Number(price.toFixed(2)),
        total_value_eur: Number(totalValue.toFixed(2)),
        total_cost_eur: Number(group.totalCost.toFixed(2)),
        unrealized_pnl_eur: Number((totalValue - group.totalCost).toFixed(2)),
        actual_pct: 0, // Computed below
        target_pct: targetPct,
        drift_pct: 0, // Computed below
        recommended_action_eur: 0,
      });
    }
  }

  // 5. Total Portfolio Equity
  const totalEquity = totalHoldingsValue + Math.max(0, latestCashBalance);

  // If no deposits were recognized, estimate net invested from total cost + cash
  let netInvested = totalDeposits - totalWithdrawals;
  if (netInvested <= 0) {
    netInvested = totalActiveCost + Math.max(0, latestCashBalance);
  }

  // Compute actual percentages and drift
  const targetMap: Record<string, number> = {};
  const currentValMap: Record<string, number> = {};
  const pricesMap: Record<string, number> = {};

  for (const h of activeHoldingsList) {
    const actualPct = totalEquity > 0 ? (h.total_value_eur / totalEquity) * 100 : 0;
    h.actual_pct = Number(actualPct.toFixed(1));
    h.drift_pct = Number((h.actual_pct - h.target_pct).toFixed(1));

    targetMap[h.symbol] = h.target_pct;
    currentValMap[h.symbol] = h.total_value_eur;
    pricesMap[h.symbol] = h.current_price_eur;
  }

  // Calculate recommended rebalance actions using baseline deposit
  const rebalancePlan = calculateDepositPlan({
    depositAmount: 800,
    portfolioValue: totalEquity,
    rebalancingTargets: targetMap,
    currentValues: currentValMap,
    prices: pricesMap,
  });
  for (const h of activeHoldingsList) {
    h.recommended_action_eur = rebalancePlan.recommendedBuys[h.symbol] || 0;
  }

  // Sort holdings by total value descending
  activeHoldingsList.sort((a, b) => b.total_value_eur - a.total_value_eur);

  // 6. Build Daily Portfolio History from dates
  const historyMap = new Map<
    string,
    {
      date: string;
      total_equity_eur: number;
      invested_capital_eur: number;
      cash_balance_eur: number;
      unrealized_pnl_eur: number;
      unrealized_pnl_pct: number;
    }
  >();

  // Collect distinct transaction dates
  const distinctDates = Array.from(new Set(sorted.map((t) => t.date).filter(Boolean))).sort();
  if (distinctDates.length > 0) {
    let runningInvested = 0;
    for (const d of distinctDates) {
      const txsOnDay = sorted.filter((t) => t.date === d);
      for (const t of txsOnDay) {
        if (isDepositTransaction(t)) {
          runningInvested += Math.abs(t.amount || t.value || 0);
        } else if (isWithdrawalTransaction(t)) {
          runningInvested -= Math.abs(t.amount || t.value || 0);
        }
      }
      const dayInvested = runningInvested > 0 ? runningInvested : netInvested;
      historyMap.set(d, {
        date: d,
        total_equity_eur: Number(totalEquity.toFixed(2)),
        invested_capital_eur: Number(dayInvested.toFixed(2)),
        cash_balance_eur: Number(latestCashBalance.toFixed(2)),
        unrealized_pnl_eur: Number((totalEquity - dayInvested).toFixed(2)),
        unrealized_pnl_pct:
          dayInvested > 0 ? Number((((totalEquity - dayInvested) / dayInvested) * 100).toFixed(2)) : 0,
      });
    }
  }

  const history: PortfolioDailyHistoryRecord[] = Array.from(historyMap.values());
  if (history.length === 0) {
    const today = new Date().toISOString().slice(0, 10);
    history.push({
      date: today,
      total_equity_eur: Number(totalEquity.toFixed(2)),
      invested_capital_eur: Number(netInvested.toFixed(2)),
      cash_balance_eur: Number(latestCashBalance.toFixed(2)),
      unrealized_pnl_eur: Number((totalEquity - netInvested).toFixed(2)),
      unrealized_pnl_pct:
        netInvested > 0 ? Number((((totalEquity - netInvested) / netInvested) * 100).toFixed(2)) : 0,
    });
  }

  const metrics = calculatePortfolioMetrics(history, activeHoldingsList);

  return {
    metrics,
    history,
    holdings: activeHoldingsList,
    assetSettings,
    isDemo: false,
    lastUpdated: new Date().toISOString(),
  };
}
