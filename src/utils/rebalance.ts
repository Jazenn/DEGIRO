import { CurrentAssetHoldingRecord, PortfolioAssetSetting } from '../types/portfolio';

export interface DepositPlanInput {
  depositAmount: number;
  portfolioValue: number;
  rebalancingTargets: Record<string, number>;
  currentValues: Record<string, number>;
  prices?: Record<string, number>;
  allowSelling?: boolean;
  roundToWholeShares?: boolean;
  isCrypto?: Record<string, boolean> | ((symbol: string) => boolean);
  currentShares?: Record<string, number>;
}

export interface DepositPlanResult {
  recommendedBuys: Record<string, number>;
  estimatedShares: Record<string, number>;
  totalBuyEur: number;
  portfolioValueAfter: number;
  underweightAssets: string[];
  recommendedSells?: Record<string, number>;
  estimatedSharesToSell?: Record<string, number>;
  totalSellEur?: number;
  netCashFlowEur?: number;
  overweightAssets?: string[];
  unallocatedCashEur?: number;
}

export type RebalanceAssetStatus = 'underweight' | 'balanced' | 'overweight';
export type RebalanceAction = 'BUY' | 'SELL' | 'HOLD';

export interface RebalanceAsset {
  symbol: string;
  name: string;
  isin?: string | null;
  currentPriceEur: number;
  currentValueEur: number;
  targetPct: number;
  actualPct: number;
  driftPct: number;
  recommendedBuyEur: number;
  estimatedShares: number;
  status: RebalanceAssetStatus;
  projectedValueEur: number;
  projectedPct: number;
  projectedDriftPct: number;
  isCrypto?: boolean;
  action?: RebalanceAction;
  recommendedSellEur?: number;
  sharesToBuy?: number;
  sharesToSell?: number;
}

export type RebalanceItem = RebalanceAsset;

export interface RebalancePlan {
  depositAmount: number;
  portfolioValueBefore: number;
  portfolioValueAfter: number;
  totalBuyEur: number;
  underweightAssets: string[];
  assets: RebalanceAsset[];
  items?: RebalanceAsset[];
  postRebalanceMaxDriftPct: number;
  allowSelling?: boolean;
  totalSellEur?: number;
  netCashFlowEur?: number;
  overweightAssets?: string[];
  unallocatedCashEur?: number;
}

export interface RebalanceOptions {
  allowSelling?: boolean;
  roundToWholeShares?: boolean;
  assetSettings?: PortfolioAssetSetting[];
}

/**
 * Normalizes weight mappings, filtering out non-positive or invalid weights.
 */
function normalizeWeights(weights: Record<string, number>): Record<string, number> {
  const normalized: Record<string, number> = {};
  for (const [symbol, weight] of Object.entries(weights || {})) {
    const val = Number(weight);
    if (!Number.isNaN(val) && val > 0) {
      normalized[symbol] = val;
    }
  }
  return normalized;
}

/**
 * Checks whether an asset is a cryptocurrency (bought/sold in exact amounts)
 * versus a stock/ETF (bought/sold in whole integer shares on DEGIRO).
 */
export function isCryptoSymbol(symbol: string, name?: string): boolean {
  const sym = (symbol || '').toUpperCase();
  const n = (name || '').toUpperCase();
  return (
    sym.includes('BTC') ||
    sym.includes('ETH') ||
    sym.includes('BITCOIN') ||
    sym.includes('ETHEREUM') ||
    sym.includes('CRYPTO') ||
    n.includes('BITCOIN') ||
    n.includes('ETHEREUM') ||
    n.includes('CRYPTO')
  );
}

export function checkIsCrypto(
  symbol: string,
  holdings?: CurrentAssetHoldingRecord[],
  assetSettings?: PortfolioAssetSetting[],
  isCryptoOption?: Record<string, boolean> | ((symbol: string) => boolean)
): boolean {
  if (isCryptoOption) {
    if (typeof isCryptoOption === 'function') return isCryptoOption(symbol);
    if (typeof isCryptoOption[symbol] === 'boolean') return isCryptoOption[symbol];
  }
  if (assetSettings) {
    const s = assetSettings.find(
      (item) => item.symbol === symbol || item.display_name === symbol
    );
    if (s && typeof s.is_crypto === 'boolean') return s.is_crypto;
  }
  if (holdings) {
    const h = holdings.find((item) => item.symbol === symbol || item.name === symbol);
    if (h && typeof h.is_crypto === 'boolean') return h.is_crypto;
    if (h) return isCryptoSymbol(h.symbol, h.name);
  }
  return isCryptoSymbol(symbol);
}

/**
 * Deposit and rebalancing distribution calculator.
 * - When allowSelling is false: allocates capital strictly to underweight assets proportionally.
 * - When allowSelling is true: recommends selling overweight assets to unlock additional capital.
 * - When roundToWholeShares is true: non-crypto assets (stocks/ETFs) can ONLY be bought or sold
 *   in whole integer shares (0, 1, 2, ...), while crypto assets are traded in exact amounts.
 */
export function calculateDepositPlan(input: DepositPlanInput): DepositPlanResult {
  const deposit = Math.max(0, Number(input.depositAmount) || 0);
  const portfolioValue = Math.max(0, Number(input.portfolioValue) || 0);
  const allowSelling = Boolean(input.allowSelling);
  const roundToWholeShares = Boolean(input.roundToWholeShares);
  const currentValues = input.currentValues || {};
  const prices = input.prices || {};
  const currentShares = input.currentShares || {};

  const allSymbols = Array.from(
    new Set([...Object.keys(currentValues), ...Object.keys(input.rebalancingTargets || {})])
  );

  const initMap = (): Record<string, number> => {
    const res: Record<string, number> = {};
    for (const sym of allSymbols) res[sym] = 0;
    return res;
  };

  const recommendedBuys: Record<string, number> = initMap();
  const estimatedShares: Record<string, number> = initMap();
  const recommendedSells: Record<string, number> = initMap();
  const estimatedSharesToSell: Record<string, number> = initMap();

  if (deposit <= 0 && !allowSelling) {
    return {
      recommendedBuys,
      estimatedShares,
      totalBuyEur: 0,
      portfolioValueAfter: portfolioValue,
      underweightAssets: [],
      recommendedSells,
      estimatedSharesToSell,
      totalSellEur: 0,
      netCashFlowEur: 0,
      overweightAssets: [],
      unallocatedCashEur: 0,
    };
  }

  const normalizedTargets = normalizeWeights(input.rebalancingTargets);
  const totalTargetWeight = Object.values(normalizedTargets).reduce((a, b) => a + b, 0);

  if (totalTargetWeight <= 0) {
    return {
      recommendedBuys,
      estimatedShares,
      totalBuyEur: 0,
      portfolioValueAfter: portfolioValue,
      underweightAssets: [],
      recommendedSells,
      estimatedSharesToSell,
      totalSellEur: 0,
      netCashFlowEur: 0,
      overweightAssets: [],
      unallocatedCashEur: 0,
    };
  }

  const projectedTotal = portfolioValue + deposit;
  const targetValues: Record<string, number> = {};

  for (const [sym, weight] of Object.entries(normalizedTargets)) {
    targetValues[sym] = projectedTotal * (weight / totalTargetWeight);
  }

  // Calculate sells if allowSelling is true
  const overweightAssets: string[] = [];
  let totalSellEur = 0;

  if (allowSelling) {
    for (const [sym, targetVal] of Object.entries(targetValues)) {
      const currentVal = Number(currentValues[sym]) || 0;
      if (currentVal > targetVal + 0.01) {
        const excess = currentVal - targetVal;
        const price = Number(prices[sym]) || 0;
        const isCrypto = checkIsCrypto(sym, undefined, undefined, input.isCrypto);
        const sharesHeld =
          typeof currentShares[sym] === 'number'
            ? currentShares[sym]
            : price > 0
            ? currentVal / price
            : 0;

        if (isCrypto) {
          // Exact amount for crypto
          const sellAmount = Math.min(excess, currentVal);
          recommendedSells[sym] = sellAmount;
          estimatedSharesToSell[sym] = price > 0 ? sellAmount / price : 0;
          totalSellEur += sellAmount;
          overweightAssets.push(sym);
        } else if (roundToWholeShares) {
          // Whole shares for stocks
          if (price > 0) {
            const idealSellShares = excess / price;
            let sharesToSell = Math.round(idealSellShares);
            sharesToSell = Math.min(sharesToSell, Math.floor(sharesHeld));
            sharesToSell = Math.max(0, sharesToSell);
            if (sharesToSell > 0) {
              const sellAmount = sharesToSell * price;
              recommendedSells[sym] = sellAmount;
              estimatedSharesToSell[sym] = sharesToSell;
              totalSellEur += sellAmount;
              overweightAssets.push(sym);
            }
          }
        } else {
          // Continuous selling
          const sellAmount = Math.min(excess, currentVal);
          recommendedSells[sym] = sellAmount;
          estimatedSharesToSell[sym] = price > 0 ? sellAmount / price : 0;
          totalSellEur += sellAmount;
          overweightAssets.push(sym);
        }
      }
    }
  }

  const availableCash = deposit + totalSellEur;

  // Identify underweight assets taking into account any sells
  const gaps: Record<string, number> = {};
  let totalGap = 0;
  const underweightAssets: string[] = [];

  for (const [sym, targetVal] of Object.entries(targetValues)) {
    const currentValAfterSell = (Number(currentValues[sym]) || 0) - (recommendedSells[sym] || 0);
    if (currentValAfterSell < targetVal - 0.01) {
      const gap = targetVal - currentValAfterSell;
      underweightAssets.push(sym);
      gaps[sym] = gap;
      totalGap += gap;
    }
  }

  if (availableCash <= 0 || underweightAssets.length === 0 || totalGap <= 0) {
    return {
      recommendedBuys,
      estimatedShares,
      totalBuyEur: 0,
      portfolioValueAfter: projectedTotal,
      underweightAssets: [],
      recommendedSells,
      estimatedSharesToSell,
      totalSellEur,
      netCashFlowEur: -totalSellEur,
      overweightAssets,
      unallocatedCashEur: Math.max(0, availableCash),
    };
  }

  // Scenario A: Continuous proportional allocation (default / when roundToWholeShares is false)
  if (!roundToWholeShares) {
    for (const sym of underweightAssets) {
      const shareOfCash = availableCash * (gaps[sym] / totalGap);
      recommendedBuys[sym] = Math.max(0, shareOfCash);
      const price = Number(prices[sym]) || 0;
      estimatedShares[sym] = price > 0 ? recommendedBuys[sym] / price : 0;
    }

    const totalBuyEur = Object.values(recommendedBuys).reduce((a, b) => a + b, 0);

    return {
      recommendedBuys,
      estimatedShares,
      totalBuyEur,
      portfolioValueAfter: projectedTotal,
      underweightAssets,
      recommendedSells,
      estimatedSharesToSell,
      totalSellEur,
      netCashFlowEur: totalBuyEur - totalSellEur,
      overweightAssets,
      unallocatedCashEur: 0,
    };
  }

  // Scenario B: Whole shares for stocks, exact for crypto
  const stockSymbols = underweightAssets.filter(
    (sym) => !checkIsCrypto(sym, undefined, undefined, input.isCrypto)
  );
  const cryptoSymbols = underweightAssets.filter(
    (sym) => checkIsCrypto(sym, undefined, undefined, input.isCrypto)
  );

  let remainingCash = availableCash;

  // Step 1: Base integer shares for stocks
  for (const sym of stockSymbols) {
    const price = Number(prices[sym]) || 0;
    if (price <= 0) continue;
    const idealBuyEur = availableCash * (gaps[sym] / totalGap);
    const idealShares = idealBuyEur / price;
    const wholeShares = Math.floor(idealShares);
    recommendedBuys[sym] = wholeShares * price;
    estimatedShares[sym] = wholeShares;
    remainingCash -= recommendedBuys[sym];
  }

  // Step 2: If all stocks got 0 shares (e.g. deposit was €100 for €124.80 Vanguard All-World),
  // round the top underweight stock to 1 whole share if ideal shares >= 0.5
  const totalStockShares = stockSymbols.reduce(
    (acc, s) => acc + (estimatedShares[s] || 0),
    0
  );
  if (stockSymbols.length > 0 && totalStockShares === 0) {
    const sortedStocks = [...stockSymbols].sort(
      (a, b) => (gaps[b] || 0) - (gaps[a] || 0)
    );
    const topStock = sortedStocks[0];
    const price = Number(prices[topStock]) || 0;
    if (price > 0) {
      const idealShares = (availableCash * (gaps[topStock] / totalGap)) / price;
      if (idealShares >= 0.5) {
        estimatedShares[topStock] = 1;
        recommendedBuys[topStock] = price;
        remainingCash -= price;
      }
    }
  }

  // Step 3: Greedily allocate remaining cash to underweight stocks if remaining cash >= stock price
  let progress = true;
  while (progress && remainingCash > 0) {
    progress = false;
    let bestStock: string | null = null;
    let maxGapRem = 0;
    for (const s of stockSymbols) {
      const p = Number(prices[s]) || 0;
      if (p > 0 && p <= remainingCash) {
        const currentVal =
          (Number(currentValues[s]) || 0) + (recommendedBuys[s] || 0);
        const gapRem = (targetValues[s] || 0) - currentVal;
        if (gapRem > maxGapRem) {
          maxGapRem = gapRem;
          bestStock = s;
        }
      }
    }
    if (bestStock && maxGapRem > 0) {
      const p = Number(prices[bestStock]) || 0;
      estimatedShares[bestStock] += 1;
      recommendedBuys[bestStock] += p;
      remainingCash -= p;
      progress = true;
    }
  }

  // Step 4: Allocate remaining cash to underweight crypto in exact amounts
  if (cryptoSymbols.length > 0 && remainingCash > 0) {
    const totalCryptoGap = cryptoSymbols.reduce((sum, s) => sum + (gaps[s] || 0), 0);
    for (const s of cryptoSymbols) {
      const price = Number(prices[s]) || 0;
      const shareOfCrypto =
        totalCryptoGap > 0
          ? remainingCash * ((gaps[s] || 0) / totalCryptoGap)
          : remainingCash / cryptoSymbols.length;
      recommendedBuys[s] = (recommendedBuys[s] || 0) + shareOfCrypto;
      estimatedShares[s] = price > 0 ? recommendedBuys[s] / price : 0;
    }
    remainingCash = 0;
  } else if (cryptoSymbols.length > 0 && totalStockShares === 0 && availableCash > 0) {
    const totalCryptoGap = cryptoSymbols.reduce((sum, s) => sum + (gaps[s] || 0), 0);
    for (const s of cryptoSymbols) {
      const price = Number(prices[s]) || 0;
      const shareOfCrypto =
        totalCryptoGap > 0
          ? availableCash * ((gaps[s] || 0) / totalCryptoGap)
          : availableCash / cryptoSymbols.length;
      recommendedBuys[s] = shareOfCrypto;
      estimatedShares[s] = price > 0 ? recommendedBuys[s] / price : 0;
    }
    remainingCash = 0;
  }

  const totalBuyEur = Object.values(recommendedBuys).reduce((a, b) => a + b, 0);

  return {
    recommendedBuys,
    estimatedShares,
    totalBuyEur,
    portfolioValueAfter: projectedTotal,
    underweightAssets,
    recommendedSells,
    estimatedSharesToSell,
    totalSellEur,
    netCashFlowEur: totalBuyEur - totalSellEur,
    overweightAssets,
    unallocatedCashEur: Math.max(0, remainingCash),
  };
}

/**
 * Calculates a complete rebalancing plan from a list of current asset holdings.
 */
export function calculateRebalancePlan(
  depositAmount: number,
  holdings: CurrentAssetHoldingRecord[],
  totalPortfolioValue?: number,
  options?: RebalanceOptions
): RebalancePlan {
  const deposit = Math.max(0, Number(depositAmount) || 0);
  const allowSelling = Boolean(options?.allowSelling);
  const roundToWholeShares = options?.roundToWholeShares ?? true;

  if (!holdings || holdings.length === 0) {
    return {
      depositAmount: deposit,
      portfolioValueBefore: 0,
      portfolioValueAfter: deposit,
      totalBuyEur: 0,
      underweightAssets: [],
      assets: [],
      items: [],
      postRebalanceMaxDriftPct: 0,
      allowSelling,
      totalSellEur: 0,
      netCashFlowEur: 0,
      overweightAssets: [],
      unallocatedCashEur: deposit,
    };
  }

  const totalCurrentValue =
    typeof totalPortfolioValue === 'number'
      ? totalPortfolioValue
      : holdings.reduce((sum, h) => sum + (Number(h.total_value_eur) || 0), 0);

  const rebalancingTargets: Record<string, number> = {};
  const currentValues: Record<string, number> = {};
  const prices: Record<string, number> = {};
  const currentShares: Record<string, number> = {};
  const isCryptoMap: Record<string, boolean> = {};

  for (const h of holdings) {
    rebalancingTargets[h.symbol] = Number(h.target_pct) || 0;
    currentValues[h.symbol] = Number(h.total_value_eur) || 0;
    prices[h.symbol] = Number(h.current_price_eur) || 0;
    currentShares[h.symbol] = Number(h.shares_held) || 0;
    isCryptoMap[h.symbol] = checkIsCrypto(
      h.symbol,
      holdings,
      options?.assetSettings
    );
  }

  const planResult = calculateDepositPlan({
    depositAmount: deposit,
    portfolioValue: totalCurrentValue,
    rebalancingTargets,
    currentValues,
    prices,
    allowSelling,
    roundToWholeShares,
    isCrypto: isCryptoMap,
    currentShares,
  });

  const projectedTotal = planResult.portfolioValueAfter;

  const assets: RebalanceAsset[] = holdings.map((h) => {
    const buyEur = planResult.recommendedBuys[h.symbol] || 0;
    const sharesToBuy = planResult.estimatedShares[h.symbol] || 0;
    const sellEur = planResult.recommendedSells?.[h.symbol] || 0;
    const sharesToSell = planResult.estimatedSharesToSell?.[h.symbol] || 0;
    const isCrypto = isCryptoMap[h.symbol] ?? false;

    const netDelta = buyEur - sellEur;
    const projectedVal = (Number(h.total_value_eur) || 0) + netDelta;
    const projectedPct =
      projectedTotal > 0 ? (projectedVal / projectedTotal) * 100 : 0;
    const projectedDrift = projectedPct - (Number(h.target_pct) || 0);

    const actualPct = Number(h.actual_pct) || 0;
    const targetPct = Number(h.target_pct) || 0;
    const driftPct =
      typeof h.drift_pct === 'number' ? h.drift_pct : actualPct - targetPct;

    let status: RebalanceAssetStatus = 'balanced';
    if (driftPct < -0.05) {
      status = 'underweight';
    } else if (driftPct > 0.05) {
      status = 'overweight';
    }

    let action: RebalanceAction = 'HOLD';
    if (buyEur > 0) {
      action = 'BUY';
    } else if (sellEur > 0) {
      action = 'SELL';
    }

    return {
      symbol: h.symbol,
      name: h.name,
      isin: h.isin,
      currentPriceEur: Number(h.current_price_eur) || 0,
      currentValueEur: Number(h.total_value_eur) || 0,
      targetPct,
      actualPct,
      driftPct,
      recommendedBuyEur: buyEur,
      estimatedShares: sharesToBuy,
      recommendedSellEur: sellEur,
      sharesToBuy,
      sharesToSell,
      action,
      isCrypto,
      status,
      projectedValueEur: projectedVal,
      projectedPct,
      projectedDriftPct: projectedDrift,
    };
  });

  const postRebalanceMaxDriftPct =
    assets.length > 0
      ? Math.max(...assets.map((i) => Math.abs(i.projectedDriftPct)))
      : 0;

  return {
    depositAmount: deposit,
    portfolioValueBefore: totalCurrentValue,
    portfolioValueAfter: projectedTotal,
    totalBuyEur: planResult.totalBuyEur,
    underweightAssets: planResult.underweightAssets,
    assets,
    items: assets,
    postRebalanceMaxDriftPct,
    allowSelling,
    totalSellEur: planResult.totalSellEur || 0,
    netCashFlowEur: planResult.netCashFlowEur ?? planResult.totalBuyEur,
    overweightAssets: planResult.overweightAssets || [],
    unallocatedCashEur: planResult.unallocatedCashEur || 0,
  };
}
