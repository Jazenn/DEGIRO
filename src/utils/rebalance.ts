import { CurrentAssetHoldingRecord } from '../types/portfolio';

export interface DepositPlanInput {
  depositAmount: number;
  portfolioValue: number;
  rebalancingTargets: Record<string, number>;
  currentValues: Record<string, number>;
  prices?: Record<string, number>;
}

export interface DepositPlanResult {
  recommendedBuys: Record<string, number>;
  estimatedShares: Record<string, number>;
  totalBuyEur: number;
  portfolioValueAfter: number;
  underweightAssets: string[];
}

export type RebalanceAssetStatus = 'underweight' | 'balanced' | 'overweight';

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
 * Mathematical deposit distribution calculator.
 * Allocates capital strictly to underweight assets proportionally to their shortfalls.
 * Invariant: Non-negative buys (>= 0) and zero sells (never recommends selling).
 */
export function calculateDepositPlan(input: DepositPlanInput): DepositPlanResult {
  const deposit = Math.max(0, Number(input.depositAmount) || 0);
  const portfolioValue = Math.max(0, Number(input.portfolioValue) || 0);
  const currentValues = input.currentValues || {};
  const prices = input.prices || {};

  const allSymbols = Array.from(
    new Set([...Object.keys(currentValues), ...Object.keys(input.rebalancingTargets || {})])
  );

  const initEmptyBuys = (): Record<string, number> => {
    const res: Record<string, number> = {};
    for (const sym of allSymbols) res[sym] = 0;
    return res;
  };

  const initEmptyShares = (): Record<string, number> => {
    const res: Record<string, number> = {};
    for (const sym of allSymbols) res[sym] = 0;
    return res;
  };

  if (deposit <= 0) {
    return {
      recommendedBuys: initEmptyBuys(),
      estimatedShares: initEmptyShares(),
      totalBuyEur: 0,
      portfolioValueAfter: portfolioValue,
      underweightAssets: [],
    };
  }

  const normalizedTargets = normalizeWeights(input.rebalancingTargets);
  const totalTargetWeight = Object.values(normalizedTargets).reduce((a, b) => a + b, 0);

  if (totalTargetWeight <= 0) {
    return {
      recommendedBuys: initEmptyBuys(),
      estimatedShares: initEmptyShares(),
      totalBuyEur: 0,
      portfolioValueAfter: portfolioValue,
      underweightAssets: [],
    };
  }

  const projectedTotal = portfolioValue + deposit;
  const targetValues: Record<string, number> = {};

  for (const [sym, weight] of Object.entries(normalizedTargets)) {
    targetValues[sym] = projectedTotal * (weight / totalTargetWeight);
  }

  const underweightAssets = Object.keys(normalizedTargets).filter((sym) => {
    const current = Number(currentValues[sym]) || 0;
    const target = targetValues[sym] || 0;
    return current < target;
  });

  if (underweightAssets.length === 0) {
    return {
      recommendedBuys: initEmptyBuys(),
      estimatedShares: initEmptyShares(),
      totalBuyEur: 0,
      portfolioValueAfter: projectedTotal,
      underweightAssets: [],
    };
  }

  let totalGap = 0;
  const gaps: Record<string, number> = {};
  for (const sym of underweightAssets) {
    const current = Number(currentValues[sym]) || 0;
    const target = targetValues[sym] || 0;
    const gap = Math.max(0, target - current);
    gaps[sym] = gap;
    totalGap += gap;
  }

  if (totalGap <= 0) {
    return {
      recommendedBuys: initEmptyBuys(),
      estimatedShares: initEmptyShares(),
      totalBuyEur: 0,
      portfolioValueAfter: projectedTotal,
      underweightAssets: [],
    };
  }

  const recommendedBuys: Record<string, number> = initEmptyBuys();
  const estimatedShares: Record<string, number> = initEmptyShares();

  for (const sym of underweightAssets) {
    const shareOfDeposit = deposit * (gaps[sym] / totalGap);
    recommendedBuys[sym] = Math.max(0, shareOfDeposit);

    const price = Number(prices[sym]) || 0;
    if (price > 0) {
      estimatedShares[sym] = recommendedBuys[sym] / price;
    } else {
      estimatedShares[sym] = 0;
    }
  }

  const totalBuyEur = Object.values(recommendedBuys).reduce((a, b) => a + b, 0);

  return {
    recommendedBuys,
    estimatedShares,
    totalBuyEur,
    portfolioValueAfter: projectedTotal,
    underweightAssets,
  };
}

/**
 * Calculates a complete rebalancing plan from a list of current asset holdings.
 */
export function calculateRebalancePlan(
  depositAmount: number,
  holdings: CurrentAssetHoldingRecord[],
  totalPortfolioValue?: number
): RebalancePlan {
  const deposit = Math.max(0, Number(depositAmount) || 0);

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
    };

  }

  const totalCurrentValue =
    typeof totalPortfolioValue === 'number'
      ? totalPortfolioValue
      : holdings.reduce((sum, h) => sum + (Number(h.total_value_eur) || 0), 0);

  const rebalancingTargets: Record<string, number> = {};
  const currentValues: Record<string, number> = {};
  const prices: Record<string, number> = {};

  for (const h of holdings) {
    rebalancingTargets[h.symbol] = Number(h.target_pct) || 0;
    currentValues[h.symbol] = Number(h.total_value_eur) || 0;
    prices[h.symbol] = Number(h.current_price_eur) || 0;
  }

  const planResult = calculateDepositPlan({
    depositAmount: deposit,
    portfolioValue: totalCurrentValue,
    rebalancingTargets,
    currentValues,
    prices,
  });

  const projectedTotal = planResult.portfolioValueAfter;

  const assets: RebalanceAsset[] = holdings.map((h) => {
    const buyEur = planResult.recommendedBuys[h.symbol] || 0;
    const shares = planResult.estimatedShares[h.symbol] || 0;
    const projectedVal = (Number(h.total_value_eur) || 0) + buyEur;
    const projectedPct = projectedTotal > 0 ? (projectedVal / projectedTotal) * 100 : 0;
    const projectedDrift = projectedPct - (Number(h.target_pct) || 0);

    const actualPct = Number(h.actual_pct) || 0;
    const targetPct = Number(h.target_pct) || 0;
    const driftPct = typeof h.drift_pct === 'number' ? h.drift_pct : actualPct - targetPct;

    let status: RebalanceAssetStatus = 'balanced';
    if (driftPct < -0.05) {
      status = 'underweight';
    } else if (driftPct > 0.05) {
      status = 'overweight';
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
      estimatedShares: shares,
      status,
      projectedValueEur: projectedVal,
      projectedPct,
      projectedDriftPct: projectedDrift,
    };
  });

  const postRebalanceMaxDriftPct = assets.length > 0
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
  };
}
