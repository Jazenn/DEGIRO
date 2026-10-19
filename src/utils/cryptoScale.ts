export type CryptoScaleStatus = 'BUY_ZONE' | 'PROFIT_ZONE' | 'NEUTRAL';

export interface CryptoScaleStatusBadge {
  label: string;
  color: 'emerald' | 'rose' | 'amber' | 'slate';
}

export interface CryptoScaleInput {
  currentPrice: number;
  buyDipTrigger: number | null;
  sellProfitTrigger: number | null;
  buyBudget: number | null;
}

export interface CryptoScaleMetrics {
  currentPrice: number;
  buyDipTrigger: number | null;
  sellProfitTrigger: number | null;
  buyBudget: number | null;
  distanceToBuyPct: number | null;
  distanceToSellPct: number | null;
  status: CryptoScaleStatus;
  statusBadge: CryptoScaleStatusBadge;
  progressPct: number;
}

/**
 * Calculates Crypto Scale metrics (domain term: Crypto Scale).
 * Evaluates current price relative to dip accumulation buy zones and take-profit targets.
 */
export function calculateCryptoScaleMetrics(
  input: CryptoScaleInput
): CryptoScaleMetrics {
  const currentPrice = Number(input.currentPrice) || 0;
  const buyDipTrigger =
    input.buyDipTrigger !== null && input.buyDipTrigger !== undefined
      ? Number(input.buyDipTrigger)
      : null;
  const sellProfitTrigger =
    input.sellProfitTrigger !== null && input.sellProfitTrigger !== undefined
      ? Number(input.sellProfitTrigger)
      : null;
  const buyBudget =
    input.buyBudget !== null && input.buyBudget !== undefined
      ? Number(input.buyBudget)
      : null;

  let distanceToBuyPct: number | null = null;
  let distanceToSellPct: number | null = null;
  let status: CryptoScaleStatus = 'NEUTRAL';
  let statusBadge: CryptoScaleStatusBadge = {
    label: 'Accumulation Range',
    color: 'amber',
  };
  let progressPct = 50;

  if (currentPrice > 0) {
    if (buyDipTrigger !== null && buyDipTrigger > 0) {
      distanceToBuyPct = ((buyDipTrigger - currentPrice) / currentPrice) * 100;
    }
    if (sellProfitTrigger !== null && sellProfitTrigger > 0) {
      distanceToSellPct = ((sellProfitTrigger - currentPrice) / currentPrice) * 100;
    }

    if (buyDipTrigger !== null && currentPrice <= buyDipTrigger) {
      status = 'BUY_ZONE';
      statusBadge = {
        label: 'Accumulation Zone Active',
        color: 'emerald',
      };
      progressPct = 0;
    } else if (sellProfitTrigger !== null && currentPrice >= sellProfitTrigger) {
      status = 'PROFIT_ZONE';
      statusBadge = {
        label: 'Profit Target Reached',
        color: 'rose',
      };
      progressPct = 100;
    } else if (
      buyDipTrigger !== null &&
      sellProfitTrigger !== null &&
      sellProfitTrigger > buyDipTrigger
    ) {
      status = 'NEUTRAL';
      statusBadge = {
        label: 'Accumulation Range',
        color: 'amber',
      };
      const range = sellProfitTrigger - buyDipTrigger;
      const progress = ((currentPrice - buyDipTrigger) / range) * 100;
      progressPct = Math.max(0, Math.min(100, progress));
    }
  }

  return {
    currentPrice,
    buyDipTrigger,
    sellProfitTrigger,
    buyBudget,
    distanceToBuyPct,
    distanceToSellPct,
    status,
    statusBadge,
    progressPct,
  };
}
