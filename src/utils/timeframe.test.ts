import { describe, it, expect } from 'vitest';
import { filterPortfolioHistory, getAssetPortfolioHistory, parseTransactionDateTime } from './timeframe';
import { PortfolioDailyHistoryRecord } from '../types/portfolio';

describe('Timeframe Filter Logic', () => {
  const sampleHistory: PortfolioDailyHistoryRecord[] = [
    {
      date: '2025-01-15',
      total_equity_eur: 30000,
      invested_capital_eur: 28000,
      cash_balance_eur: 500,
      unrealized_pnl_eur: 2000,
      unrealized_pnl_pct: 7.14,
    },
    {
      date: '2025-06-01',
      total_equity_eur: 35000,
      invested_capital_eur: 32000,
      cash_balance_eur: 800,
      unrealized_pnl_eur: 3000,
      unrealized_pnl_pct: 9.38,
    },
    {
      date: '2025-10-15',
      total_equity_eur: 38000,
      invested_capital_eur: 35000,
      cash_balance_eur: 1000,
      unrealized_pnl_eur: 3000,
      unrealized_pnl_pct: 8.57,
    },
    {
      date: '2026-07-15',
      total_equity_eur: 44000,
      invested_capital_eur: 40000,
      cash_balance_eur: 1200,
      unrealized_pnl_eur: 4000,
      unrealized_pnl_pct: 10.0,
    },
    {
      date: '2026-09-15',
      total_equity_eur: 46000,
      invested_capital_eur: 41000,
      cash_balance_eur: 1300,
      unrealized_pnl_eur: 5000,
      unrealized_pnl_pct: 12.2,
    },
    {
      date: '2026-10-10',
      total_equity_eur: 47500,
      invested_capital_eur: 42000,
      cash_balance_eur: 1400,
      unrealized_pnl_eur: 5500,
      unrealized_pnl_pct: 13.1,
    },
    {
      date: '2026-10-19',
      total_equity_eur: 48250,
      invested_capital_eur: 42238,
      cash_balance_eur: 1420,
      unrealized_pnl_eur: 6012,
      unrealized_pnl_pct: 14.23,
    },
  ];

  const refDate = new Date('2026-10-19T12:00:00Z');

  it('returns all records sorted by date for ALL timeframe', () => {
    // Pass in reverse order to ensure sorting works
    const reversed = [...sampleHistory].reverse();
    const result = filterPortfolioHistory(reversed, 'ALL', refDate);

    expect(result.length).toBe(7);
    expect(result[0].date).toBe('2025-01-15');
    expect(result[result.length - 1].date).toBe('2026-10-19');
  });

  it('filters to the last 1 month for 1M timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '1M', refDate);
    // cutoff: 2026-09-19 -> includes 2026-10-10 and 2026-10-19
    expect(result.map((r) => r.date)).toEqual(['2026-10-10', '2026-10-19']);
  });

  it('filters to the last 3 months for 3M timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '3M', refDate);
    // cutoff: 2026-07-19 -> includes 2026-09-15, 2026-10-10, 2026-10-19
    expect(result.map((r) => r.date)).toEqual([
      '2026-09-15',
      '2026-10-10',
      '2026-10-19',
    ]);
  });

  it('filters to the last 1 year for 1Y timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '1Y', refDate);
    // cutoff: 2026-10-19 minus 1 year = 2025-10-19
    // includes 2026-07-15, 2026-09-15, 2026-10-10, 2026-10-19
    expect(result.map((r) => r.date)).toEqual([
      '2026-07-15',
      '2026-09-15',
      '2026-10-10',
      '2026-10-19',
    ]);
  });

  it('defaults to latest date in history when referenceDate is not provided', () => {
    const result = filterPortfolioHistory(sampleHistory, '1M');
    expect(result.map((r) => r.date)).toEqual(['2026-10-10', '2026-10-19']);
  });

  it('handles empty history gracefully', () => {
    const result = filterPortfolioHistory([], '1M');
    expect(result).toEqual([]);
  });

  it('returns all available points if history span is shorter than timeframe', () => {
    const shortHistory = sampleHistory.slice(-2);
    const result = filterPortfolioHistory(shortHistory, '1Y', refDate);
    expect(result.length).toBe(2);
  });

  it('filters to the last 1 week for 1W timeframe', () => {
    const result = filterPortfolioHistory(sampleHistory, '1W', refDate);
    // cutoff: 2026-10-19 minus 7 days = 2026-10-12 -> includes 2026-10-19
    expect(result.map((r) => r.date)).toEqual(['2026-10-19']);
  });

  it('generates 15-minute interval points across 24H timeframe ending at reference time', () => {
    const nowRef = new Date('2026-10-21T11:22:00.000Z');
    const result = filterPortfolioHistory(sampleHistory, '24H', nowRef);

    expect(result.length).toBe(98);

    const lastPoint = result[result.length - 1];
    expect(new Date(lastPoint.date).toISOString()).toBe('2026-10-21T11:22:00.000Z');
    expect(lastPoint.total_equity_eur).toBe(48250);

    const secondLastPoint = result[result.length - 2];
    expect(new Date(secondLastPoint.date).toISOString()).toBe('2026-10-21T11:15:00.000Z');

    const firstPoint = result[0];
    expect(new Date(firstPoint.date).toISOString()).toBe('2026-10-20T11:15:00.000Z');

    for (let i = 0; i < 96; i++) {
      const diff = new Date(result[i + 1].date).getTime() - new Date(result[i].date).getTime();
      expect(diff).toBe(15 * 60 * 1000);
    }
  });

  it('renders an instant drop-off (step change) when an asset sell occurs instead of a gradual decline', () => {
    const btcSellHistory: PortfolioDailyHistoryRecord[] = [
      {
        date: '2026-10-20',
        total_equity_eur: 800,
        invested_capital_eur: 700,
        cash_balance_eur: 100,
        unrealized_pnl_eur: 100,
        unrealized_pnl_pct: 14.29,
      },
      {
        date: '2026-10-21',
        total_equity_eur: 600,
        invested_capital_eur: 500,
        cash_balance_eur: 300,
        unrealized_pnl_eur: 100,
        unrealized_pnl_pct: 20.0,
      },
    ];

    const nowRef = new Date('2026-10-21T11:22:00.000Z');
    const sellTransaction = {
      date: '21-10-2026',
      time: '09:30',
      product: 'BITCOIN',
      isin: null,
      description: 'Verkoop Bitcoin 0.003 @ 66666.67',
      amount: 200,
      quantity: -0.003,
      price: 66666.67,
    };

    const result = filterPortfolioHistory(btcSellHistory, '24H', nowRef, {
      transactions: [sellTransaction as any],
      selectedAsset: 'BTC-EUR',
    });

    const sellTime = parseTransactionDateTime('21-10-2026', '09:30')!.getTime();

    const pointsBeforeSell = result.filter(
      (p) => new Date(p.date).getTime() < sellTime
    );
    expect(pointsBeforeSell.length).toBeGreaterThan(0);
    for (const p of pointsBeforeSell) {
      expect(p.total_equity_eur).toBeGreaterThan(790);
      expect(p.total_equity_eur).toBeLessThan(810);
    }

    const pointsAfterSell = result.filter(
      (p) => new Date(p.date).getTime() >= sellTime
    );
    expect(pointsAfterSell.length).toBeGreaterThan(0);
    for (const p of pointsAfterSell) {
      expect(p.total_equity_eur).toBeGreaterThan(590);
      expect(p.total_equity_eur).toBeLessThan(610);
    }
  });
});

describe('getAssetPortfolioHistory', () => {
  const historyWithBreakdown: PortfolioDailyHistoryRecord[] = [
    {
      date: '2025-01-01',
      total_equity_eur: 1000,
      invested_capital_eur: 1000,
      cash_balance_eur: 1000,
      unrealized_pnl_eur: 0,
      unrealized_pnl_pct: 0,
      asset_breakdown: {},
    },
    {
      date: '2025-02-01',
      total_equity_eur: 1200,
      invested_capital_eur: 1000,
      cash_balance_eur: 200,
      unrealized_pnl_eur: 200,
      unrealized_pnl_pct: 20,
      asset_breakdown: {
        'BTC-EUR': {
          value_eur: 1000,
          cost_eur: 800,
          shares: 0.05,
          price_eur: 20000,
          pnl_eur: 200,
          pnl_pct: 25,
        },
      },
    },
    {
      date: '2025-03-01',
      total_equity_eur: 1500,
      invested_capital_eur: 1000,
      cash_balance_eur: 200,
      unrealized_pnl_eur: 500,
      unrealized_pnl_pct: 50,
      asset_breakdown: {
        'BTC-EUR': {
          value_eur: 1300,
          cost_eur: 800,
          shares: 0.05,
          price_eur: 26000,
          pnl_eur: 500,
          pnl_pct: 62.5,
        },
      },
    },
  ];

  it('returns original history when assetKey is null or ALL', () => {
    expect(getAssetPortfolioHistory(historyWithBreakdown, null)).toEqual(historyWithBreakdown);
    expect(getAssetPortfolioHistory(historyWithBreakdown, 'ALL')).toEqual(historyWithBreakdown);
  });

  it('filters to individual asset valuation and trims leading empty dates', () => {
    const btcHistory = getAssetPortfolioHistory(historyWithBreakdown, 'BTC-EUR');
    // Leading date 2025-01-01 had 0 BTC, should be trimmed to start from 2025-02-01
    expect(btcHistory.length).toBe(2);
    expect(btcHistory[0].date).toBe('2025-02-01');
    expect(btcHistory[0].total_equity_eur).toBe(1000);
    expect(btcHistory[0].invested_capital_eur).toBe(800);
    expect(btcHistory[0].unrealized_pnl_eur).toBe(200);

    expect(btcHistory[1].date).toBe('2025-03-01');
    expect(btcHistory[1].total_equity_eur).toBe(1300);
    expect(btcHistory[1].unrealized_pnl_eur).toBe(500);
  });

  it('resolves crypto and ETF aliases when filtering asset history', () => {
    // Breakdown stored under BITCOIN should be found when querying BTC-EUR
    const btcAliasHistory = getAssetPortfolioHistory(
      [
        {
          date: '2025-02-01',
          total_equity_eur: 1000,
          invested_capital_eur: 800,
          cash_balance_eur: 0,
          unrealized_pnl_eur: 200,
          unrealized_pnl_pct: 25,
          asset_breakdown: {
            BITCOIN: {
              value_eur: 1000,
              cost_eur: 800,
              shares: 0.05,
              price_eur: 20000,
              pnl_eur: 200,
              pnl_pct: 25,
            },
          },
        },
      ],
      'BTC-EUR'
    );
    expect(btcAliasHistory.length).toBe(1);
    expect(btcAliasHistory[0].total_equity_eur).toBe(1000);

    // Breakdown stored under IE000OJ5TQP4 should be found when querying ASWC.DE
    const fodAliasHistory = getAssetPortfolioHistory(
      [
        {
          date: '2026-01-16',
          total_equity_eur: 182,
          invested_capital_eur: 180,
          cash_balance_eur: 0,
          unrealized_pnl_eur: 2,
          unrealized_pnl_pct: 1.1,
          asset_breakdown: {
            IE000OJ5TQP4: {
              value_eur: 182,
              cost_eur: 180,
              shares: 10,
              price_eur: 18.2,
              pnl_eur: 2,
              pnl_pct: 1.1,
            },
          },
        },
      ],
      'ASWC.DE'
    );
    expect(fodAliasHistory.length).toBe(1);
    expect(fodAliasHistory[0].total_equity_eur).toBe(182);
  });
});
