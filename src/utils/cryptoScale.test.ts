import { describe, it, expect } from 'vitest';
import { calculateCryptoScaleMetrics } from './cryptoScale';

describe('cryptoScale', () => {
  it('calculates distance percentages and neutral status for price within band', () => {
    // Current price €64,320, buy dip trigger €58,500, sell profit target €75,420, budget €350
    const metrics = calculateCryptoScaleMetrics({
      currentPrice: 64320,
      buyDipTrigger: 58500,
      sellProfitTrigger: 75420,
      buyBudget: 350,
    });

    expect(metrics.status).toBe('NEUTRAL');
    expect(metrics.statusBadge.label).toMatch(/Accumulation Range|Neutral/i);

    // Distance to buy: (58500 - 64320) / 64320 * 100 = -9.05%
    expect(metrics.distanceToBuyPct).toBeCloseTo(-9.05, 1);

    // Distance to sell: (75420 - 64320) / 64320 * 100 = +17.26%
    expect(metrics.distanceToSellPct).toBeCloseTo(17.26, 1);

    // Progress percentage between 58500 and 75420: (64320 - 58500) / (75420 - 58500) * 100 = 34.4%
    expect(metrics.progressPct).toBeCloseTo(34.4, 0.5);
    expect(metrics.buyBudget).toBe(350);
  });

  it('detects BUY_ZONE when current price is at or below the dip buy trigger', () => {
    const metrics = calculateCryptoScaleMetrics({
      currentPrice: 58000,
      buyDipTrigger: 58500,
      sellProfitTrigger: 75420,
      buyBudget: 350,
    });

    expect(metrics.status).toBe('BUY_ZONE');
    expect(metrics.statusBadge.label).toMatch(/Accumulation Zone Active|Buy Zone/i);
    expect(metrics.progressPct).toBe(0);
    expect(metrics.distanceToBuyPct).toBeGreaterThanOrEqual(0); // At or below trigger
  });

  it('detects PROFIT_ZONE when current price is at or above the profit target', () => {
    const metrics = calculateCryptoScaleMetrics({
      currentPrice: 76000,
      buyDipTrigger: 58500,
      sellProfitTrigger: 75420,
      buyBudget: 350,
    });

    expect(metrics.status).toBe('PROFIT_ZONE');
    expect(metrics.statusBadge.label).toMatch(/Profit Target Reached|Profit Zone/i);
    expect(metrics.progressPct).toBe(100);
    expect(metrics.distanceToSellPct).toBeLessThanOrEqual(0);
  });

  it('handles missing or null triggers safely', () => {
    const metrics = calculateCryptoScaleMetrics({
      currentPrice: 3200,
      buyDipTrigger: null,
      sellProfitTrigger: null,
      buyBudget: null,
    });

    expect(metrics.status).toBe('NEUTRAL');
    expect(metrics.distanceToBuyPct).toBeNull();
    expect(metrics.distanceToSellPct).toBeNull();
    expect(metrics.progressPct).toBe(50);
  });
});
