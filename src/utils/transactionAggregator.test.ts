import { describe, it, expect } from 'vitest';
import { calculateDashboardFromTransactions } from './transactionAggregator';
import { IngestedTransaction } from './csvParser';
import { PortfolioAssetSetting } from '../types/portfolio';

describe('calculateDashboardFromTransactions', () => {
  const mockSettings: PortfolioAssetSetting[] = [
    {
      symbol: 'IE00BK5BQT80',
      display_name: 'Vanguard FTSE All-World UCITS ETF',
      target_pct: 60.0,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'IE00B4K48X80',
      display_name: 'iShares Core MSCI Europe',
      target_pct: 40.0,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
  ];

  it('returns null for empty transactions array', () => {
    expect(calculateDashboardFromTransactions([], mockSettings)).toBeNull();
  });

  it('calculates portfolio valuation, cash balance, and holdings from real transactions', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2026-01-05',
        time: '09:00',
        product: 'DEGIRO',
        isin: 'NLFLATEXACNT',
        description: 'Storting iDEAL',
        amount: 5000,
        value: 5000,
        balance: 5000,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'hash-1',
      },
      {
        date: '2026-01-06',
        time: '10:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 20 @ 100',
        amount: -2000,
        value: -2000,
        balance: 3000,
        quantity: 20,
        price: 100,
        orderId: 'order-1',
        rowHash: 'hash-2',
      },
      {
        date: '2026-01-07',
        time: '10:30',
        product: 'iShares Core MSCI Europe',
        isin: 'IE00B4K48X80',
        description: 'Koop 10 @ 100',
        amount: -1000,
        value: -1000,
        balance: 2000,
        quantity: 10,
        price: 100,
        orderId: 'order-2',
        rowHash: 'hash-3',
      },
    ];

    const result = calculateDashboardFromTransactions(transactions, mockSettings);
    expect(result).not.toBeNull();
    if (!result) return;

    expect(result.isDemo).toBe(false);
    expect(result.metrics.freeCashBalance).toBe(2000); // Latest Saldo
    expect(result.metrics.totalPortfolioValue).toBe(5000); // 2000 VWCE + 1000 IMAE + 2000 cash
    expect(result.metrics.netInvestedCapital).toBe(5000);
    expect(result.holdings.length).toBe(2);

    const vwce = result.holdings.find((h) => h.isin === 'IE00BK5BQT80');
    expect(vwce).toBeDefined();
    expect(vwce?.shares_held).toBe(20);
    expect(vwce?.total_value_eur).toBe(2000);
  });

  it('correctly reduces shares held on sales', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2026-01-05',
        time: '09:00',
        product: 'DEGIRO',
        isin: 'NLFLATEXACNT',
        description: 'Storting iDEAL',
        amount: 2000,
        value: 2000,
        balance: 2000,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'hash-1',
      },
      {
        date: '2026-01-06',
        time: '10:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 10 @ 100',
        amount: -1000,
        value: -1000,
        balance: 1000,
        quantity: 10,
        price: 100,
        orderId: 'order-1',
        rowHash: 'hash-2',
      },
      {
        date: '2026-01-10',
        time: '14:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Verkoop 4 @ 110',
        amount: 440,
        value: 440,
        balance: 1440,
        quantity: 4,
        price: 110,
        orderId: 'order-3',
        rowHash: 'hash-3',
      },
    ];

    const result = calculateDashboardFromTransactions(transactions, mockSettings);
    expect(result).not.toBeNull();
    if (!result) return;

    const vwce = result.holdings.find((h) => h.isin === 'IE00BK5BQT80');
    expect(vwce?.shares_held).toBe(6); // 10 - 4
    expect(vwce?.current_price_eur).toBe(110);
    expect(vwce?.total_value_eur).toBe(660); // 6 * 110
    expect(result.metrics.freeCashBalance).toBe(1440);
    expect(result.metrics.totalPortfolioValue).toBe(2100); // 660 + 1440
  });

  it('calculates portfolio metrics when quantity and price are null and embedded in description (Account.csv)', () => {
    // Reverse chronological order with European dates as typical in DEGIRO exports
    const transactions: IngestedTransaction[] = [
      {
        date: '10-02-2026',
        time: '14:30',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 10 @ 110,00 EUR',
        amount: -1100,
        value: -1100,
        balance: 1000,
        quantity: null,
        price: null,
        orderId: 'ORD-3',
        rowHash: 'hash-c',
      },
      {
        date: '02-02-2026',
        time: '11:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 20 @ 100,00 EUR',
        amount: -2000,
        value: -2000,
        balance: 2100,
        quantity: null,
        price: null,
        orderId: 'ORD-2',
        rowHash: 'hash-b',
      },
      {
        date: '01-02-2026',
        time: '09:00',
        product: 'DEGIRO',
        isin: 'NLFLATEXACNT',
        description: 'Overboeking van uw geldrekening',
        amount: 4100,
        value: 4100,
        balance: 4100,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'hash-a',
      },
    ];

    const result = calculateDashboardFromTransactions(transactions, mockSettings);
    expect(result).not.toBeNull();
    if (!result) return;

    // Latest cash balance should be 1000 (from 10-02-2026)
    expect(result.metrics.freeCashBalance).toBe(1000);
    // VWCE: 20 @ 100 + 10 @ 110 = 30 shares @ 110 latest price = 3300 value
    expect(result.holdings.length).toBe(1);
    expect(result.holdings[0].shares_held).toBe(30);
    expect(result.holdings[0].current_price_eur).toBe(110);
    expect(result.holdings[0].total_value_eur).toBe(3300);
    // Total portfolio value = 3300 holdings + 1000 cash = 4300
    expect(result.metrics.totalPortfolioValue).toBe(4300);
    // Net invested = 4100 deposit
    expect(result.metrics.netInvestedCapital).toBe(4100);
    // Total gain = 4300 - 4100 = 200
    expect(result.metrics.totalGainLossEur).toBe(200);
  });
});
