import { describe, it, expect } from 'vitest';
import {
  calculateDepositPlan,
  calculateRebalancePlan,
} from './rebalance';
import { CurrentAssetHoldingRecord } from '../types/portfolio';

describe('Rebalance Calculation Seam', () => {
  const sampleTargets = {
    'VWCE.DE': 60,
    'BTC-EUR': 20,
    'IMAE.AS': 20,
  };

  const samplePrices = {
    'VWCE.DE': 120.0,
    'BTC-EUR': 60000.0,
    'IMAE.AS': 80.0,
  };

  describe('calculateDepositPlan - Core Math & Invariants', () => {
    it('allocates deposit proportionally across underweight assets', () => {
      // Portfolio value = 1000. Deposit = 500. Projected total = 1500.
      // Target values: VWCE (60%) = 900, BTC (20%) = 300, IMAE (20%) = 300.
      // Current values: VWCE = 400, BTC = 400, IMAE = 200.
      // Shortfalls: VWCE = 900 - 400 = 500. BTC = 300 - 400 = -100 (overweight -> 0).
      //             IMAE = 300 - 200 = 100.
      // Total gap = 500 + 100 = 600.
      // Recommended buys for 500 deposit:
      // VWCE: 500 * (500 / 600) = 416.6667
      // IMAE: 500 * (100 / 600) = 83.3333
      // BTC: 0
      const currentValues = {
        'VWCE.DE': 400.0,
        'BTC-EUR': 400.0,
        'IMAE.AS': 200.0,
      };

      const result = calculateDepositPlan({
        depositAmount: 500.0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      expect(result.totalBuyEur).toBeCloseTo(500.0, 2);
      expect(result.recommendedBuys['VWCE.DE']).toBeCloseTo(416.67, 2);
      expect(result.recommendedBuys['IMAE.AS']).toBeCloseTo(83.33, 2);
      expect(result.recommendedBuys['BTC-EUR']).toBe(0);
      expect(result.underweightAssets).toEqual(['VWCE.DE', 'IMAE.AS']);
      expect(result.portfolioValueAfter).toBeCloseTo(1500.0, 2);

      // Verify estimated shares:
      // VWCE: 416.6667 / 120 = ~3.47 shares
      // IMAE: 83.3333 / 80 = ~1.04 shares
      // BTC: 0 shares
      expect(result.estimatedShares['VWCE.DE']).toBeCloseTo(416.6667 / 120.0, 2);
      expect(result.estimatedShares['IMAE.AS']).toBeCloseTo(83.3333 / 80.0, 2);
      expect(result.estimatedShares['BTC-EUR']).toBe(0);
    });

    it('strictly enforces non-negative buys and zero sells on overweight assets', () => {
      // BTC is heavily overweight (80% vs 20% target)
      const currentValues = {
        'VWCE.DE': 100.0,
        'BTC-EUR': 800.0,
        'IMAE.AS': 100.0,
      };

      const result = calculateDepositPlan({
        depositAmount: 200.0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      // No asset should ever receive a negative purchase (selling is forbidden)
      for (const buyEur of Object.values(result.recommendedBuys)) {
        expect(buyEur).toBeGreaterThanOrEqual(0);
      }
      expect(result.recommendedBuys['BTC-EUR']).toBe(0);
      expect(result.estimatedShares['BTC-EUR']).toBe(0);
      expect(result.totalBuyEur).toBeCloseTo(200.0, 2);
    });

    it('handles zero or negative deposit edge case gracefully', () => {
      const currentValues = {
        'VWCE.DE': 400.0,
        'BTC-EUR': 400.0,
        'IMAE.AS': 200.0,
      };

      const zeroResult = calculateDepositPlan({
        depositAmount: 0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      expect(zeroResult.totalBuyEur).toBe(0);
      expect(zeroResult.portfolioValueAfter).toBe(1000.0);
      expect(zeroResult.recommendedBuys['VWCE.DE']).toBe(0);
      expect(zeroResult.recommendedBuys['BTC-EUR']).toBe(0);
      expect(zeroResult.recommendedBuys['IMAE.AS']).toBe(0);
      expect(zeroResult.estimatedShares['VWCE.DE']).toBe(0);
      expect(zeroResult.underweightAssets).toEqual([]);

      const negativeResult = calculateDepositPlan({
        depositAmount: -100,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      expect(negativeResult.totalBuyEur).toBe(0);
      expect(negativeResult.portfolioValueAfter).toBe(1000.0);
      expect(negativeResult.underweightAssets).toEqual([]);
    });

    it('handles all assets balanced edge case', () => {
      // Total = 1000. Exactly 60%, 20%, 20%
      const currentValues = {
        'VWCE.DE': 600.0,
        'BTC-EUR': 200.0,
        'IMAE.AS': 200.0,
      };

      // When deposit = 0 or when already perfectly balanced with zero gap
      // If deposit = 300, projected total = 1300.
      // Target values: 780, 260, 260.
      // All assets are underweight relative to the new capital!
      // But if deposit = 0, no buys:
      const resultNoDeposit = calculateDepositPlan({
        depositAmount: 0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });
      expect(resultNoDeposit.totalBuyEur).toBe(0);

      // If all targets are 0 or empty:
      const resultZeroTargets = calculateDepositPlan({
        depositAmount: 500.0,
        portfolioValue: 1000.0,
        rebalancingTargets: { 'VWCE.DE': 0, 'BTC-EUR': 0 },
        currentValues: { 'VWCE.DE': 500, 'BTC-EUR': 500 },
      });
      expect(resultZeroTargets.totalBuyEur).toBe(0);
      expect(resultZeroTargets.underweightAssets).toEqual([]);
    });

    it('handles single underweight asset by allocating 100% of deposit to it', () => {
      // VWCE is at 600 (target 60%), BTC is at 300 (target 20% -> 200, so overweight)
      // IMAE is at 100 (target 20% -> 200, so underweight)
      // Deposit = 200. Projected = 1200.
      // Targets: VWCE = 720 (gap = 120), BTC = 240 (gap = 0), IMAE = 240 (gap = 140).
      // Here two are underweight. Let's construct a true single underweight case:
      // VWCE: 800 (target 60% of 1000 is 600, of 1100 is 660 -> overweight)
      // BTC: 250 (target 20% of 1000 is 200, of 1100 is 220 -> overweight)
      // IMAE: 50 (target 20% of 1000 is 200, of 1100 is 220 -> underweight)
      // Deposit: 100. Projected: 1200.
      // VWCE target: 720 (< 800) -> overweight
      // BTC target: 240 (< 250) -> overweight
      // IMAE target: 240 (> 50) -> underweight (gap = 190)
      const currentValues = {
        'VWCE.DE': 800.0,
        'BTC-EUR': 250.0,
        'IMAE.AS': 50.0,
      };

      const result = calculateDepositPlan({
        depositAmount: 100.0,
        portfolioValue: 1100.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      expect(result.underweightAssets).toEqual(['IMAE.AS']);
      expect(result.recommendedBuys['IMAE.AS']).toBeCloseTo(100.0, 2);
      expect(result.recommendedBuys['VWCE.DE']).toBe(0);
      expect(result.recommendedBuys['BTC-EUR']).toBe(0);
      expect(result.totalBuyEur).toBeCloseTo(100.0, 2);
      expect(result.estimatedShares['IMAE.AS']).toBeCloseTo(100.0 / 80.0, 2);
    });

    it('handles deposit larger than drift without breaking non-negative constraints', () => {
      // Small drift: VWCE shortfall is 20, IMAE shortfall is 10.
      // Deposit is huge: 5000 EUR!
      const currentValues = {
        'VWCE.DE': 580.0,
        'BTC-EUR': 250.0,
        'IMAE.AS': 170.0,
      };

      const result = calculateDepositPlan({
        depositAmount: 5000.0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      expect(result.totalBuyEur).toBeCloseTo(5000.0, 2);
      // All buys must be non-negative
      for (const buyEur of Object.values(result.recommendedBuys)) {
        expect(buyEur).toBeGreaterThanOrEqual(0);
      }
      expect(result.portfolioValueAfter).toBeCloseTo(6000.0, 2);
    });

    it('normalizes rebalancing targets regardless of scale (decimal vs percent vs custom)', () => {
      // 0.60, 0.20, 0.20 vs 60, 20, 20
      const currentValues = {
        'VWCE.DE': 400.0,
        'BTC-EUR': 400.0,
        'IMAE.AS': 200.0,
      };

      const decimalTargets = {
        'VWCE.DE': 0.6,
        'BTC-EUR': 0.2,
        'IMAE.AS': 0.2,
      };

      const planDecimal = calculateDepositPlan({
        depositAmount: 500.0,
        portfolioValue: 1000.0,
        rebalancingTargets: decimalTargets,
        currentValues,
        prices: samplePrices,
      });

      const planPercent = calculateDepositPlan({
        depositAmount: 500.0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });

      expect(planDecimal.recommendedBuys['VWCE.DE']).toBeCloseTo(
        planPercent.recommendedBuys['VWCE.DE'],
        4
      );
      expect(planDecimal.recommendedBuys['IMAE.AS']).toBeCloseTo(
        planPercent.recommendedBuys['IMAE.AS'],
        4
      );
    });
  });

  describe('calculateRebalancePlan - High-Level Holdings Seam', () => {
    const mockHoldings: CurrentAssetHoldingRecord[] = [
      {
        symbol: 'VWCE.DE',
        name: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        shares_held: 200,
        current_price_eur: 125.0,
        total_value_eur: 25000.0,
        total_cost_eur: 22000.0,
        unrealized_pnl_eur: 3000.0,
        actual_pct: 50.0,
        target_pct: 60.0,
        drift_pct: -10.0,
        recommended_action_eur: 0,
      },
      {
        symbol: 'BTC-EUR',
        name: 'Bitcoin',
        isin: 'XFC000A2YY6Q',
        shares_held: 0.25,
        current_price_eur: 60000.0,
        total_value_eur: 15000.0,
        total_cost_eur: 12000.0,
        unrealized_pnl_eur: 3000.0,
        actual_pct: 30.0,
        target_pct: 20.0,
        drift_pct: 10.0,
        recommended_action_eur: 0,
      },
      {
        symbol: 'IMAE.AS',
        name: 'iShares European Property Yield',
        isin: 'IE00B4K48X80',
        shares_held: 125,
        current_price_eur: 80.0,
        total_value_eur: 10000.0,
        total_cost_eur: 9000.0,
        unrealized_pnl_eur: 1000.0,
        actual_pct: 20.0,
        target_pct: 20.0,
        drift_pct: 0.0,
        recommended_action_eur: 0,
      },
    ];

    it('generates rich RebalanceAsset records with drift indicators and estimated shares', () => {
      // Total value = 50,000 EUR. Deposit = 800 EUR.
      const plan = calculateRebalancePlan(800, mockHoldings);

      expect(plan.depositAmount).toBe(800);
      expect(plan.portfolioValueBefore).toBe(50000);
      expect(plan.portfolioValueAfter).toBe(50800);
      expect(plan.totalBuyEur).toBeCloseTo(800, 2);

      expect(plan.assets).toHaveLength(3);

      const vwce = plan.assets.find((i) => i.symbol === 'VWCE.DE')!;
      expect(vwce).toBeDefined();
      expect(vwce.status).toBe('underweight');
      expect(vwce.recommendedBuyEur).toBeCloseTo(777.30, 2);
      expect(vwce.estimatedShares).toBeCloseTo(777.30 / 125.0, 2);
      expect(vwce.driftPct).toBeCloseTo(-10.0, 1);
      expect(vwce.projectedPct).toBeGreaterThan(vwce.actualPct);

      const btc = plan.assets.find((i) => i.symbol === 'BTC-EUR')!;
      expect(btc.status).toBe('overweight');
      expect(btc.recommendedBuyEur).toBe(0);
      expect(btc.estimatedShares).toBe(0);

      const imae = plan.assets.find((i) => i.symbol === 'IMAE.AS')!;
      expect(imae.recommendedBuyEur).toBeCloseTo(22.70, 2);
      expect(imae.estimatedShares).toBeCloseTo(22.70 / 80.0, 2);
    });

    it('calculates post-rebalance drift and detects convergence towards target', () => {
      const plan = calculateRebalancePlan(2000, mockHoldings);

      expect(plan.postRebalanceMaxDriftPct).toBeLessThan(10.0);
    });

    it('handles empty holdings list safely', () => {
      const plan = calculateRebalancePlan(500, []);

      expect(plan.depositAmount).toBe(500);
      expect(plan.portfolioValueBefore).toBe(0);
      expect(plan.portfolioValueAfter).toBe(500);
      expect(plan.totalBuyEur).toBe(0);
      expect(plan.assets).toEqual([]);
      expect(plan.underweightAssets).toEqual([]);
    });
  });
});
