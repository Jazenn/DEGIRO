import {
  AssetDaySnapshot,
  CurrentAssetHoldingRecord,
  DashboardData,
  PortfolioAssetSetting,
  PortfolioDailyHistoryRecord,
} from '../types/portfolio';
import {
  IngestedTransaction,
  extractTradeFromDescription,
  isInternalCashSweep,
  normalizeDate,
} from './csvParser';
import { calculatePortfolioMetrics } from './metrics';
import { calculateDepositPlan } from './rebalance';

/**
 * Normalizes string values for fuzzy matching.
 */
function normalizeString(val: string | null | undefined): string {
  return (val || '').toLowerCase().trim();
}

/**
 * Checks if a transaction is an internal cash sweep or non-position record.
 * Internal Flatex cash sweeps (Degiro Cash Sweep Transfer, Overboeking, FLATEX EURO BANKACCOUNT)
 * are net-zero transfers that must NOT distort invested capital or cash ledger.
 * Real stocks like Aegon are NOT internal cash sweeps.
 */
export function isInternalCashTransaction(tx: IngestedTransaction): boolean {
  if (tx.isCashSweep !== undefined) {
    return tx.isCashSweep;
  }
  return isInternalCashSweep(tx.description, tx.product);
}

/**
 * Checks if a transaction is an external deposit (money transferred into DEGIRO from external bank).
 * Excludes internal cash sweeps and Flatex bank transfers.
 * Includes 3-row iDEAL deposit lifecycle (+X Reservation, -X Reservation Release, +X Settled Deposit).
 */
export function isDepositTransaction(tx: IngestedTransaction): boolean {
  if (isInternalCashTransaction(tx)) {
    return false;
  }
  const desc = normalizeString(tx.description);
  if (
    desc.includes('flatexdegiro bank') ||
    desc.includes('cash sweep') ||
    desc.includes('overboeking')
  ) {
    return false;
  }
  return (
    desc.includes('ideal') ||
    desc.includes('deposit') ||
    (desc.includes('storting') && !desc.includes('terugstorting'))
  );
}

/**
 * Checks if a transaction is an external withdrawal (money transferred out to external bank).
 * Excludes internal cash sweeps.
 */
export function isWithdrawalTransaction(tx: IngestedTransaction): boolean {
  if (isInternalCashTransaction(tx)) {
    return false;
  }
  const desc = normalizeString(tx.description);
  if (
    desc.includes('flatexdegiro bank') ||
    desc.includes('cash sweep')
  ) {
    return false;
  }
  return (
    desc === 'terugstorting' ||
    desc.startsWith('terugstorting') ||
    (desc.includes('onttrekking') && !desc.includes('flatex')) ||
    (desc.includes('withdrawal') && !desc.includes('flatex'))
  );
}

/**
 * Sort transactions forward in time using DEGIRO tie-breaking rules.
 * Primary: Datetime (date + time) ASC
 * Tie-breaker: csv_row_id DESC (original DEGIRO export is reverse chronological,
 * so higher row index within the same minute executed earlier).
 */
export function sortTransactionsChronologically(
  transactions: IngestedTransaction[]
): IngestedTransaction[] {
  return [...transactions].sort((a, b) => {
    const da = normalizeDate(a.date || '');
    const db = normalizeDate(b.date || '');
    const dateComp = da.localeCompare(db);
    if (dateComp !== 0) return dateComp;
    const timeComp = (a.time || '').localeCompare(b.time || '');
    if (timeComp !== 0) return timeComp;
    const rowA = a.csvRowId ?? 0;
    const rowB = b.csvRowId ?? 0;
    return rowB - rowA;
  });
}

/**
 * Calculate current free cash balance from non-sweep cash ledger transactions.
 * Uses Saldo if present on latest transaction, or sums non-sweep cash mutations.
 */
export function calculateCashBalance(transactions: IngestedTransaction[]): number {
  if (!transactions || transactions.length === 0) return 0;
  const sorted = sortTransactionsChronologically(transactions);

  for (let i = sorted.length - 1; i >= 0; i--) {
    const tx = sorted[i];
    if (tx.balance !== null && tx.balance !== undefined && !isNaN(tx.balance)) {
      return Number(tx.balance);
    }
  }

  let computedCash = 0;
  for (const tx of sorted) {
    if (isInternalCashTransaction(tx)) continue;
    if (tx.amount !== null && !isNaN(tx.amount)) {
      computedCash += tx.amount;
    } else if (tx.value !== null && !isNaN(tx.value)) {
      computedCash += tx.value;
    }
  }
  return Math.round(computedCash * 100) / 100;
}

/**
 * Calculate cumulative net external deposited capital.
 * Follows the 3-row iDEAL lifecycle (+X reservation, -X reservation release, +X settled deposit)
 * where internal cash sweeps are excluded. Net sum of external deposits and withdrawals.
 */
export function calculateNetInvestedCapital(transactions: IngestedTransaction[]): number {
  if (!transactions || transactions.length === 0) return 0;
  const sorted = sortTransactionsChronologically(transactions);
  let totalDeposits = 0;
  let totalWithdrawals = 0;
  let hasExternalFlow = false;

  for (const tx of sorted) {
    if (isInternalCashTransaction(tx)) continue;

    if (isDepositTransaction(tx)) {
      const amt = tx.amount !== null && !isNaN(tx.amount)
        ? tx.amount
        : tx.value !== null && !isNaN(tx.value)
        ? tx.value
        : 0;
      totalDeposits += amt;
      hasExternalFlow = true;
    } else if (isWithdrawalTransaction(tx)) {
      const amt = Math.abs(tx.amount || tx.value || 0);
      totalWithdrawals += amt;
      hasExternalFlow = true;
    }
  }

  if (!hasExternalFlow) return 0;
  return Math.round((totalDeposits - totalWithdrawals) * 100) / 100;
}

/**
 * Dynamically calculates full dashboard metrics, holdings, and portfolio history
 * directly from ingested DEGIRO transactions.
 */
export function calculateDashboardFromTransactions(
  transactions: IngestedTransaction[],
  assetSettings: PortfolioAssetSetting[] = [],
  currentPrices?: Record<string, number>
): DashboardData | null {
  if (!transactions || transactions.length === 0) {
    return null;
  }

  // 1. Sort transactions chronologically:
  // DEGIRO exports transactions newest first (line 2 of CSV is newest, line 173 is oldest).
  // When sorting chronologically (oldest to newest):
  // Date asc, Time asc.
  // For ties, higher csvRowId comes first (older in time, since CSV is exported newest-first).
  const sorted = sortTransactionsChronologically(transactions);

  // 2. Compute Cash Balance
  const latestCashBalance = calculateCashBalance(sorted);

  // 3. Compute Net Invested Capital
  let totalDeposits = 0;
  let totalWithdrawals = 0;
  let hasExternalFlow = false;
  for (const tx of sorted) {
    if (isInternalCashTransaction(tx)) continue;
    if (isDepositTransaction(tx)) {
      const amt = tx.amount !== null && !isNaN(tx.amount)
        ? tx.amount
        : tx.value !== null && !isNaN(tx.value)
        ? tx.value
        : 0;
      totalDeposits += amt;
      hasExternalFlow = true;
    } else if (isWithdrawalTransaction(tx)) {
      const amt = Math.abs(tx.amount || tx.value || 0);
      totalWithdrawals += amt;
      hasExternalFlow = true;
    }
  }

  // 4. Compute Holdings per Asset
  interface AssetTradePoint {
    date: string;
    price: number;
  }
  interface AssetGroup {
    symbol: string;
    name: string;
    isin: string | null;
    shares: number;
    totalCost: number;
    latestPrice: number;
    lots: Array<{ quantity: number; price: number }>;
    tradePrices: AssetTradePoint[];
  }
  const assetGroups = new Map<string, AssetGroup>();

  for (const tx of sorted) {
    // Skip pure cash transactions and internal account rows
    if (isInternalCashTransaction(tx)) continue;
    if (!tx.product && !tx.isin && !tx.description) continue;
    if (isDepositTransaction(tx) || isWithdrawalTransaction(tx)) continue;

    // Skip fee, dividend tax, and interest rows
    const desc = normalizeString(tx.description);
    const isFee =
      desc.includes('transactiekosten') ||
      desc.includes('kosten van derden') ||
      desc.includes('aansluitingskosten') ||
      desc.includes('valutakosten') ||
      desc.includes('fee');
    const isDividend =
      desc.includes('dividend') ||
      desc.includes('rente') ||
      desc.includes('interest');
    if (isFee || isDividend) continue;

    let rawQty =
      tx.quantity !== null && tx.quantity !== undefined
        ? Number(tx.quantity)
        : 0;
    let execPrice =
      tx.price !== null && tx.price !== undefined ? Number(tx.price) : 0;

    // If quantity or price was not in tx, try to extract from description
    if (rawQty === 0 || execPrice === 0) {
      const extracted = extractTradeFromDescription(tx.description);
      if (rawQty === 0 && extracted.quantity !== null) {
        rawQty = extracted.quantity;
      }
      if (execPrice === 0 && extracted.price !== null) {
        execPrice = extracted.price;
      }
    }

    const isSell = desc.includes('verkoop') || desc.includes('sell') || rawQty < 0;
    const absQty = Math.abs(rawQty);

    const key = (tx.isin || tx.product || 'UNKNOWN').trim().toUpperCase();
    if (!assetGroups.has(key)) {
      assetGroups.set(key, {
        symbol: tx.isin || tx.product || 'UNKNOWN',
        name: tx.product || tx.isin || 'Asset',
        isin: tx.isin || null,
        shares: 0,
        totalCost: 0,
        latestPrice: execPrice > 0 ? execPrice : Math.abs(tx.price || 0),
        lots: [] as Array<{ quantity: number; price: number }>,
        tradePrices: [] as AssetTradePoint[],
      });
    }

    const group = assetGroups.get(key)!;
    if (execPrice > 0) {
      group.latestPrice = execPrice;
      const txD = normalizeDate(tx.date);
      if (txD) {
        group.tradePrices.push({ date: txD, price: execPrice });
      }
    }

    if (absQty > 0) {
      if (isSell) {
        // FIFO lot depletion matching backend/engine/portfolio.py
        let sellQty = absQty;
        group.shares = Math.max(0, group.shares - absQty);
        while (sellQty > 0 && group.lots.length > 0) {
          const lot = group.lots[0];
          if (lot.quantity <= sellQty + 1e-9) {
            sellQty -= lot.quantity;
            group.lots.shift();
          } else {
            lot.quantity -= sellQty;
            sellQty = 0;
          }
        }
        if (group.shares <= 1e-6) {
          group.shares = 0;
          group.totalCost = 0;
          group.lots = [];
        } else {
          group.totalCost = group.lots.reduce((acc: number, lot: { quantity: number; price: number }) => acc + lot.quantity * lot.price, 0);
        }
      } else {
        // Buy: append FIFO lot
        group.shares += absQty;
        const buyCost = Math.abs(
          tx.amount !== null && tx.amount !== undefined
            ? tx.amount
            : tx.value !== null && tx.value !== undefined
            ? tx.value
            : absQty * (execPrice || group.latestPrice)
        );
        const lotPrice = execPrice > 0 ? execPrice : absQty > 0 ? buyCost / absQty : group.latestPrice;
        group.lots.push({ quantity: absQty, price: lotPrice });
        group.totalCost = group.lots.reduce((acc: number, lot: { quantity: number; price: number }) => acc + lot.quantity * lot.price, 0);
      }
    }
  }

  // Filter out closed positions (shares == 0)
  const activeHoldingsList: CurrentAssetHoldingRecord[] = [];
  let totalHoldingsValue = 0;
  let totalActiveCost = 0;

  for (const group of assetGroups.values()) {
    if (group.shares > 0.0001) {
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

      const symUpper = (group.symbol || '').toUpperCase();
      const isinUpper = (group.isin || '').toUpperCase();
      const settingSym = setting?.symbol ? setting.symbol.toUpperCase() : '';
      const settingName = setting?.display_name ? setting.display_name.toUpperCase() : '';

      const livePrice =
        (currentPrices && (
          (isinUpper && currentPrices[isinUpper]) ||
          (group.isin && currentPrices[group.isin]) ||
          (symUpper && currentPrices[symUpper]) ||
          (group.symbol && currentPrices[group.symbol]) ||
          (settingSym && currentPrices[settingSym]) ||
          (setting?.symbol && currentPrices[setting.symbol]) ||
          (settingName && currentPrices[settingName]) ||
          (setting?.display_name && currentPrices[setting.display_name]) ||
          (symUpper.includes('BTC') || symUpper.includes('BITCOIN')
            ? currentPrices['BITCOIN'] || currentPrices['BTC'] || currentPrices['BTC-EUR']
            : undefined) ||
          (symUpper.includes('ETH') || symUpper.includes('ETHEREUM')
            ? currentPrices['ETHEREUM'] || currentPrices['ETH'] || currentPrices['ETH-EUR']
            : undefined)
        )) || undefined;

      const price =
        livePrice && livePrice > 0
          ? livePrice
          : group.latestPrice > 0
          ? group.latestPrice
          : group.shares > 0
          ? group.totalCost / group.shares
          : 0;
      group.latestPrice = price;
      const totalValue = group.shares * price;
      totalHoldingsValue += totalValue;
      totalActiveCost += group.totalCost;

      const targetPct = setting ? setting.target_pct : 0;

      activeHoldingsList.push({
        symbol: setting ? setting.symbol : group.symbol,
        name: setting ? setting.display_name : group.name,
        isin: group.isin,
        shares_held: Number(group.shares.toFixed(8)),
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

  // If no external deposits were recognized, estimate net invested from total cost + cash
  let netInvested = hasExternalFlow ? totalDeposits - totalWithdrawals : 0;
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

  // 6. Build Daily Portfolio History across continuous calendar dates
  const firstTxDate = normalizeDate(sorted[0]?.date);
  const lastTxDate = normalizeDate(sorted[sorted.length - 1]?.date);
  const todayStr = new Date().toISOString().slice(0, 10);
  const startDateStr = firstTxDate || todayStr;
  const endDateStr = lastTxDate > todayStr ? lastTxDate : todayStr;

  const calendarDates: string[] = [];
  const startD = new Date(startDateStr + 'T00:00:00Z');
  const endD = new Date(endDateStr + 'T00:00:00Z');

  if (isNaN(startD.getTime()) || isNaN(endD.getTime()) || startD.getTime() > endD.getTime()) {
    calendarDates.push(todayStr);
  } else {
    const cur = new Date(startD);
    while (cur.getTime() <= endD.getTime()) {
      calendarDates.push(cur.toISOString().slice(0, 10));
      cur.setUTCDate(cur.getUTCDate() + 1);
    }
  }

  // Pre-index transactions by normalized date
  const txByDate = new Map<string, IngestedTransaction[]>();
  for (const tx of sorted) {
    const d = normalizeDate(tx.date);
    if (!d) continue;
    if (!txByDate.has(d)) txByDate.set(d, []);
    txByDate.get(d)!.push(tx);
  }

  // Helper to interpolate price for an asset on any date
  const getAssetPriceOnDate = (group: AssetGroup, dateStr: string): number => {
    if (!group.tradePrices || group.tradePrices.length === 0) {
      return group.latestPrice || 0;
    }
    const targetTime = new Date(dateStr + 'T00:00:00Z').getTime();
    const todayTime = new Date(todayStr + 'T00:00:00Z').getTime();

    if (targetTime >= todayTime) {
      return group.latestPrice || 0;
    }

    let beforeTrade: AssetTradePoint | null = null;
    let afterTrade: AssetTradePoint | null = null;

    for (const tp of group.tradePrices) {
      const tpTime = new Date(tp.date + 'T00:00:00Z').getTime();
      if (tpTime <= targetTime) {
        if (!beforeTrade || tpTime > new Date(beforeTrade.date + 'T00:00:00Z').getTime()) {
          beforeTrade = tp;
        }
      } else {
        if (!afterTrade || tpTime < new Date(afterTrade.date + 'T00:00:00Z').getTime()) {
          afterTrade = tp;
        }
      }
    }

    if (!beforeTrade) {
      return afterTrade ? afterTrade.price : group.latestPrice || 0;
    }

    if (!afterTrade) {
      const beforeTime = new Date(beforeTrade.date + 'T00:00:00Z').getTime();
      const span = todayTime - beforeTime;
      if (span <= 0) return beforeTrade.price;
      const progress = Math.min(1, Math.max(0, (targetTime - beforeTime) / span));
      return beforeTrade.price + (group.latestPrice - beforeTrade.price) * progress;
    }

    const beforeTime = new Date(beforeTrade.date + 'T00:00:00Z').getTime();
    const afterTime = new Date(afterTrade.date + 'T00:00:00Z').getTime();
    const span = afterTime - beforeTime;
    if (span <= 0) return beforeTrade.price;
    const progress = Math.min(1, Math.max(0, (targetTime - beforeTime) / span));
    return beforeTrade.price + (afterTrade.price - beforeTrade.price) * progress;
  };

  const history: PortfolioDailyHistoryRecord[] = [];
  let runningCash = 0;
  let runningInvested = 0;
  const currentShares = new Map<string, number>();
  const currentCosts = new Map<string, number>();

  for (let i = 0; i < calendarDates.length; i++) {
    const d = calendarDates[i];
    const isFinalDay = i === calendarDates.length - 1;
    const dayTxs = txByDate.get(d) || [];

    for (const tx of dayTxs) {
      if (isInternalCashTransaction(tx)) continue;

      if (isDepositTransaction(tx)) {
        const amt =
          tx.amount !== null && !isNaN(tx.amount)
            ? tx.amount
            : tx.value !== null && !isNaN(tx.value)
            ? tx.value
            : 0;
        runningInvested += amt;
      } else if (isWithdrawalTransaction(tx)) {
        runningInvested -= Math.abs(tx.amount || tx.value || 0);
      }

      if (tx.balance !== null && tx.balance !== undefined && !isNaN(tx.balance)) {
        runningCash = Number(tx.balance);
      } else {
        if (tx.amount !== null && !isNaN(tx.amount)) {
          runningCash += tx.amount;
        } else if (tx.value !== null && !isNaN(tx.value)) {
          runningCash += tx.value;
        }
      }

      if (tx.product || tx.isin || tx.description) {
        const desc = normalizeString(tx.description);
        const isFee =
          desc.includes('transactiekosten') ||
          desc.includes('kosten van derden') ||
          desc.includes('aansluitingskosten') ||
          desc.includes('valutakosten') ||
          desc.includes('fee');
        const isDividend =
          desc.includes('dividend') ||
          desc.includes('rente') ||
          desc.includes('interest');
        if (!isFee && !isDividend && !isDepositTransaction(tx) && !isWithdrawalTransaction(tx)) {
          let rawQty =
            tx.quantity !== null && tx.quantity !== undefined
              ? Number(tx.quantity)
              : 0;
          let execPrice =
            tx.price !== null && tx.price !== undefined ? Number(tx.price) : 0;
          if (rawQty === 0 || execPrice === 0) {
            const extracted = extractTradeFromDescription(tx.description);
            if (rawQty === 0 && extracted.quantity !== null) rawQty = extracted.quantity;
            if (execPrice === 0 && extracted.price !== null) execPrice = extracted.price;
          }
          const isSell = desc.includes('verkoop') || desc.includes('sell') || rawQty < 0;
          const absQty = Math.abs(rawQty);
          const key = (tx.isin || tx.product || 'UNKNOWN').trim().toUpperCase();
          if (absQty > 0) {
            const prevShares = currentShares.get(key) || 0;
            const prevCost = currentCosts.get(key) || 0;
            if (isSell) {
              const newShares = Math.max(0, prevShares - absQty);
              currentShares.set(key, newShares);
              const costReduction = prevShares > 0 ? (absQty / prevShares) * prevCost : prevCost;
              currentCosts.set(key, Math.max(0, prevCost - costReduction));
            } else {
              currentShares.set(key, prevShares + absQty);
              const buyCost = Math.abs(
                tx.amount !== null && tx.amount !== undefined
                  ? tx.amount
                  : tx.value !== null && tx.value !== undefined
                  ? tx.value
                  : absQty * execPrice
              );
              currentCosts.set(key, prevCost + buyCost);
            }
          }
        }
      }
    }

    let dayHoldingsValue = 0;
    let totalCostBasis = 0;
    const dayBreakdown: Record<string, AssetDaySnapshot> = {};

    for (const [key, shares] of currentShares.entries()) {
      const cost = currentCosts.get(key) || 0;
      if (shares > 0.0001 || cost > 0.01) {
        const group = assetGroups.get(key);
        const p = group ? getAssetPriceOnDate(group, d) : 0;
        const val = shares * p;
        dayHoldingsValue += val;
        totalCostBasis += cost;

        const pnl = val - cost;
        const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
        const snap: AssetDaySnapshot = {
          value_eur: Number(val.toFixed(2)),
          cost_eur: Number(cost.toFixed(2)),
          shares: Number(shares.toFixed(8)),
          price_eur: Number(p.toFixed(2)),
          pnl_eur: Number(pnl.toFixed(2)),
          pnl_pct: Number(pnlPct.toFixed(2)),
        };

        dayBreakdown[key] = snap;
        if (group?.symbol) dayBreakdown[group.symbol] = snap;
        if (group?.isin) dayBreakdown[group.isin] = snap;
        if (group?.name) dayBreakdown[group.name] = snap;
      }
    }

    if (isFinalDay) {
      for (const h of activeHoldingsList) {
        const snap: AssetDaySnapshot = {
          value_eur: h.total_value_eur,
          cost_eur: h.total_cost_eur,
          shares: h.shares_held,
          price_eur: h.current_price_eur,
          pnl_eur: h.unrealized_pnl_eur,
          pnl_pct:
            h.total_cost_eur > 0
              ? Number((((h.total_value_eur - h.total_cost_eur) / h.total_cost_eur) * 100).toFixed(2))
              : 0,
        };
        dayBreakdown[h.symbol] = snap;
        if (h.isin) dayBreakdown[h.isin] = snap;
        if (h.name) dayBreakdown[h.name] = snap;
      }
    }

    let dayTotalEquity = isFinalDay
      ? totalEquity
      : dayHoldingsValue + Math.max(0, runningCash);
    let dayInvested = isFinalDay
      ? netInvested
      : runningInvested > 0
      ? runningInvested
      : totalCostBasis + Math.max(0, runningCash);
    let dayCash = isFinalDay ? latestCashBalance : runningCash;

    history.push({
      date: d,
      total_equity_eur: Number(dayTotalEquity.toFixed(2)),
      invested_capital_eur: Number(dayInvested.toFixed(2)),
      cash_balance_eur: Number(dayCash.toFixed(2)),
      unrealized_pnl_eur: Number((dayTotalEquity - dayInvested).toFixed(2)),
      unrealized_pnl_pct:
        dayInvested > 0
          ? Number((((dayTotalEquity - dayInvested) / dayInvested) * 100).toFixed(2))
          : 0,
      asset_breakdown: dayBreakdown,
    });
  }

  if (history.length === 0) {
    const fallbackBreakdown: Record<string, AssetDaySnapshot> = {};
    for (const h of activeHoldingsList) {
      fallbackBreakdown[h.symbol] = {
        value_eur: h.total_value_eur,
        cost_eur: h.total_cost_eur,
        shares: h.shares_held,
        price_eur: h.current_price_eur,
        pnl_eur: h.unrealized_pnl_eur,
        pnl_pct:
          h.total_cost_eur > 0
            ? Number((((h.total_value_eur - h.total_cost_eur) / h.total_cost_eur) * 100).toFixed(2))
            : 0,
      };
      if (h.isin) fallbackBreakdown[h.isin] = fallbackBreakdown[h.symbol];
    }
    history.push({
      date: todayStr,
      total_equity_eur: Number(totalEquity.toFixed(2)),
      invested_capital_eur: Number(netInvested.toFixed(2)),
      cash_balance_eur: Number(latestCashBalance.toFixed(2)),
      unrealized_pnl_eur: Number((totalEquity - netInvested).toFixed(2)),
      unrealized_pnl_pct:
        netInvested > 0 ? Number((((totalEquity - netInvested) / netInvested) * 100).toFixed(2)) : 0,
      asset_breakdown: fallbackBreakdown,
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
