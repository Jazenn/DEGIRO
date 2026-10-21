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

      const resultNoDeposit = calculateDepositPlan({
        depositAmount: 0,
        portfolioValue: 1000.0,
        rebalancingTargets: sampleTargets,
        currentValues,
        prices: samplePrices,
      });
      expect(resultNoDeposit.totalBuyEur).toBe(0);

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
      for (const buyEur of Object.values(result.recommendedBuys)) {
        expect(buyEur).toBeGreaterThanOrEqual(0);
      }
      expect(result.portfolioValueAfter).toBeCloseTo(6000.0, 2);
    });

    it('normalizes rebalancing targets regardless of scale (decimal vs percent vs custom)', () => {
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

  describe('calculateRebalancePlan - Whole Shares & Selling Options', () => {
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
        is_crypto: false,
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
        is_crypto: true,
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
        is_crypto: false,
      },
    ];

    it('enforces whole shares for stocks (e.g. 6 whole shares for VWCE, not 6.2)', () => {
      // Total value = 50,000 EUR. Deposit = 800 EUR.
      // VWCE shortfall = ~777.30 EUR -> 6 whole shares @ 125 = 750 EUR.
      // Remaining 50 EUR cannot buy 1 share of IMAE (80 EUR), so stays unallocated.
      const plan = calculateRebalancePlan(800, mockHoldings);

      expect(plan.depositAmount).toBe(800);
      expect(plan.portfolioValueBefore).toBe(50000);
      expect(plan.portfolioValueAfter).toBe(50800);
      expect(plan.totalBuyEur).toBe(750.0);
      expect(plan.unallocatedCashEur).toBe(50.0);

      expect(plan.assets).toHaveLength(3);

      const vwce = plan.assets.find((i) => i.symbol === 'VWCE.DE')!;
      expect(vwce).toBeDefined();
      expect(vwce.status).toBe('underweight');
      expect(vwce.estimatedShares).toBe(6); // whole integer!
      expect(vwce.recommendedBuyEur).toBe(750.0);
      expect(vwce.action).toBe('BUY');

      const btc = plan.assets.find((i) => i.symbol === 'BTC-EUR')!;
      expect(btc.status).toBe('overweight');
      expect(btc.recommendedBuyEur).toBe(0);
      expect(btc.estimatedShares).toBe(0);

      const imae = plan.assets.find((i) => i.symbol === 'IMAE.AS')!;
      expect(imae.recommendedBuyEur).toBe(0);
      expect(imae.estimatedShares).toBe(0);
    });

    it('resolves fractional bug: recommends 1 whole share instead of 0.8 when deposit is near share price', () => {
      // Vanguard price is 124.80. Deposit is 100.
      // Continuous math gave 100 / 124.80 = 0.801 shares.
      // Whole share calculation yields 1 whole share (124.80 EUR).
      const singleHolding: CurrentAssetHoldingRecord[] = [
        {
          symbol: 'VWCE.DE',
          name: 'Vanguard FTSE All-World UCITS ETF',
          isin: 'IE00BK5BQT80',
          shares_held: 10,
          current_price_eur: 124.8,
          total_value_eur: 1248.0,
          total_cost_eur: 1200.0,
          unrealized_pnl_eur: 48.0,
          actual_pct: 100.0,
          target_pct: 100.0,
          drift_pct: 0.0,
          recommended_action_eur: 0,
          is_crypto: false,
        },
      ];

      const plan = calculateRebalancePlan(100, singleHolding);
      const vwce = plan.assets[0];
      expect(vwce.estimatedShares).toBe(1);
      expect(vwce.recommendedBuyEur).toBe(124.8);
    });

    it('allows continuous math when roundToWholeShares is explicitly set to false', () => {
      const plan = calculateRebalancePlan(800, mockHoldings, undefined, {
        roundToWholeShares: false,
      });

      expect(plan.totalBuyEur).toBeCloseTo(800.0, 2);
      const vwce = plan.assets.find((i) => i.symbol === 'VWCE.DE')!;
      expect(vwce.recommendedBuyEur).toBeCloseTo(777.30, 2);
      expect(vwce.estimatedShares).toBeCloseTo(777.30 / 125.0, 2);
    });

    it('allocates exact fractional amounts to underweight crypto assets', () => {
      const cryptoUnderweightHoldings: CurrentAssetHoldingRecord[] = [
        {
          symbol: 'VWCE.DE',
          name: 'Vanguard FTSE All-World',
          isin: 'IE00BK5BQT80',
          shares_held: 200,
          current_price_eur: 125.0,
          total_value_eur: 25000.0,
          total_cost_eur: 20000.0,
          unrealized_pnl_eur: 5000.0,
          actual_pct: 70.0,
          target_pct: 50.0,
          drift_pct: 20.0,
          recommended_action_eur: 0,
          is_crypto: false,
        },
        {
          symbol: 'BTC-EUR',
          name: 'Bitcoin',
          isin: 'XFC000A2YY6Q',
          shares_held: 0.1,
          current_price_eur: 60000.0,
          total_value_eur: 6000.0,
          total_cost_eur: 5000.0,
          unrealized_pnl_eur: 1000.0,
          actual_pct: 30.0,
          target_pct: 50.0,
          drift_pct: -20.0,
          recommended_action_eur: 0,
          is_crypto: true,
        },
      ];

      // Deposit = 500 EUR. BTC is underweight, VWCE is overweight.
      const plan = calculateRebalancePlan(500, cryptoUnderweightHoldings);
      const btc = plan.assets.find((i) => i.symbol === 'BTC-EUR')!;

      expect(btc.recommendedBuyEur).toBe(500);
      expect(btc.estimatedShares).toBeCloseTo(500 / 60000.0, 6); // exact fractional!
    });

    it('rebalances with sells when allowSelling is true (sells overweight BTC to buy Vanguard)', () => {
      // BTC is overweight by ~4,840 EUR.
      // With allowSelling: true, BTC is sold to fund whole share purchases of VWCE!
      const plan = calculateRebalancePlan(800, mockHoldings, undefined, {
        allowSelling: true,
      });

      expect(plan.allowSelling).toBe(true);
      expect(plan.totalSellEur).toBeGreaterThan(4000);

      const btc = plan.assets.find((i) => i.symbol === 'BTC-EUR')!;
      expect(btc.action).toBe('SELL');
      expect(btc.recommendedSellEur).toBeGreaterThan(4000);
      expect(btc.sharesToSell).toBeCloseTo(btc.recommendedSellEur! / 60000.0, 4);

      const vwce = plan.assets.find((i) => i.symbol === 'VWCE.DE')!;
      expect(vwce.action).toBe('BUY');
      // VWCE receives many whole shares funded by the BTC sell proceeds + deposit!
      expect(Number.isInteger(vwce.estimatedShares)).toBe(true);
      expect(vwce.estimatedShares).toBeGreaterThan(40);
      expect(vwce.recommendedBuyEur).toBe(vwce.estimatedShares * 125.0);

      // Max post-rebalance drift should be dramatically minimized
      expect(plan.postRebalanceMaxDriftPct).toBeLessThan(1.0);
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
