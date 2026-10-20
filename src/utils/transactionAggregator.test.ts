import { describe, it, expect } from 'vitest';
import {
  calculateDashboardFromTransactions,
  sortTransactionsChronologically,
  isInternalCashTransaction,
  calculateCashBalance,
  calculateNetInvestedCapital,
} from './transactionAggregator';
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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
        isCashSweep: false,
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

  it('does not treat AEGON stock as an internal cash sweep and includes it in active holdings', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2026-01-01',
        time: '09:00',
        product: 'DEGIRO',
        isin: '',
        description: 'iDEAL Deposit',
        amount: 500,
        value: 500,
        balance: 500,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'hash-dep',
        isCashSweep: false,
      },
      {
        date: '2026-01-02',
        time: '10:00',
        product: 'AEGON LTD.',
        isin: 'BMG0112X1056',
        description: 'Koop 50 @ 6,00 EUR',
        amount: -300,
        value: -300,
        balance: 200,
        quantity: 50,
        price: 6.0,
        orderId: 'ord-aegon',
        rowHash: 'hash-aegon',
        isCashSweep: false,
      },
    ];

    expect(isInternalCashTransaction(transactions[1])).toBe(false);
    const result = calculateDashboardFromTransactions(transactions);
    expect(result).not.toBeNull();
    const aegon = result?.holdings.find((h) => h.isin === 'BMG0112X1056' || h.symbol === 'BMG0112X1056');
    expect(aegon).toBeDefined();
    expect(aegon?.shares_held).toBe(50);
    expect(aegon?.total_value_eur).toBe(300);
  });

  it('sorts transactions forward in time using tie-breaking (date ASC, time ASC, csvRowId DESC)', () => {
    const txA: IngestedTransaction = {
      date: '2026-03-01',
      time: '10:00',
      product: 'Vanguard FTSE All-World',
      isin: 'IE00BK5BQT80',
      description: 'Koop 1 @ 100',
      amount: -100,
      value: -100,
      balance: 400,
      quantity: 1,
      price: 100,
      orderId: 'ord-1',
      rowHash: 'hash-1',
      csvRowId: 10,
      isCashSweep: false,
    };
    const txB: IngestedTransaction = {
      date: '2026-03-01',
      time: '10:00',
      product: 'Vanguard FTSE All-World',
      isin: 'IE00BK5BQT80',
      description: 'DEGIRO Transactiekosten',
      amount: -1,
      value: -1,
      balance: 399,
      quantity: null,
      price: null,
      orderId: 'ord-1',
      rowHash: 'hash-2',
      csvRowId: 9,
      isCashSweep: false,
    };

    const sorted = sortTransactionsChronologically([txB, txA]);
    expect(sorted[0].csvRowId).toBe(10);
    expect(sorted[1].csvRowId).toBe(9);
  });

  it('excludes internal cash sweeps from net invested capital and cash mutations', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2026-01-01',
        time: '09:00',
        product: '',
        isin: '',
        description: 'Reservation iDEAL',
        amount: 1000,
        value: 1000,
        balance: 1000,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'h1',
        isCashSweep: false,
      },
      {
        date: '2026-01-02',
        time: '03:00',
        product: '',
        isin: '',
        description: 'Reservation iDEAL',
        amount: -1000,
        value: -1000,
        balance: 0,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'h2',
        isCashSweep: false,
      },
      {
        date: '2026-01-02',
        time: '03:00',
        product: '',
        isin: '',
        description: 'iDEAL Deposit',
        amount: 1000,
        value: 1000,
        balance: 1000,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'h3',
        isCashSweep: false,
      },
      {
        date: '2026-01-03',
        time: '04:00',
        product: '',
        isin: '',
        description: 'Degiro Cash Sweep Transfer',
        amount: 500,
        value: 500,
        balance: 1500,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'h4',
        isCashSweep: true,
      },
      {
        date: '2026-01-03',
        time: '04:00',
        product: '',
        isin: '',
        description: 'Overboeking naar uw geldrekening bij flatexDEGIRO Bank 500 EUR',
        amount: null,
        value: null,
        balance: 1000,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'h5',
        isCashSweep: true,
      },
    ];

    const result = calculateDashboardFromTransactions(transactions);
    expect(result).not.toBeNull();
    expect(result?.metrics.netInvestedCapital).toBe(1000);
    expect(calculateNetInvestedCapital(transactions)).toBe(1000);
    expect(calculateCashBalance(transactions)).toBe(1000);
  });

  it('correctly parses and aggregates real user Account.csv file', async () => {
    const fs = await import('fs');
    const { parseDegiroCsv } = await import('./csvParser');
    if (!fs.existsSync('Account.csv')) return;
    const content = fs.readFileSync('Account.csv', 'utf-8');
    const parseResult = parseDegiroCsv(content);
    const dashboard = calculateDashboardFromTransactions(parseResult.transactions, mockSettings);
    expect(parseResult.transactions.length).toBe(172);
    expect(dashboard).not.toBeNull();
    expect(dashboard?.metrics.netInvestedCapital).toBe(3728);
    expect(dashboard?.metrics.freeCashBalance).toBe(5.96);
    expect(dashboard?.holdings.length).toBe(6);

    // Verify standalone cash and invested capital functions
    expect(calculateNetInvestedCapital(parseResult.transactions)).toBe(3728);
    expect(calculateCashBalance(parseResult.transactions)).toBe(5.96);
  });

  it('calculates FIFO cost basis and depletes oldest lots first upon partial sale', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2026-01-01',
        time: '09:00',
        product: 'DEGIRO',
        isin: '',
        description: 'iDEAL Deposit',
        amount: 1000,
        value: 1000,
        balance: 1000,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'hash-dep',
        isCashSweep: false,
        csvRowId: 0,
      },
      // Lot 1: Buy 10 @ €10 (cost = 100)
      {
        date: '2026-01-02',
        time: '10:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 10 @ 10,00 EUR',
        amount: -100,
        value: -100,
        balance: 900,
        quantity: 10,
        price: 10,
        orderId: 'ord-buy-1',
        rowHash: 'hash-buy-1',
        isCashSweep: false,
        csvRowId: 1,
      },
      // Lot 2: Buy 10 @ €20 (cost = 200)
      {
        date: '2026-01-03',
        time: '10:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 10 @ 20,00 EUR',
        amount: -200,
        value: -200,
        balance: 700,
        quantity: 10,
        price: 20,
        orderId: 'ord-buy-2',
        rowHash: 'hash-buy-2',
        isCashSweep: false,
        csvRowId: 2,
      },
      // Sell 10 @ €25 (depletes Lot 1 @ €10 under FIFO; remaining is Lot 2 @ €20)
      {
        date: '2026-01-04',
        time: '10:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Verkoop 10 @ 25,00 EUR',
        amount: 250,
        value: 250,
        balance: 950,
        quantity: -10,
        price: 25,
        orderId: 'ord-sell-1',
        rowHash: 'hash-sell-1',
        isCashSweep: false,
        csvRowId: 3,
      },
    ];

    const result = calculateDashboardFromTransactions(transactions, mockSettings);
    expect(result).not.toBeNull();
    if (!result) return;

    expect(result.holdings.length).toBe(1);
    const vwce = result.holdings[0];
    expect(vwce.shares_held).toBe(10);
    // Remaining cost basis under FIFO must be 10 * 20 = 200 (not weighted average 150)
    expect(vwce.total_cost_eur).toBe(200);
    // Current price is €25 from latest transaction
    expect(vwce.current_price_eur).toBe(25);
    // Total value = 10 * 25 = 250
    expect(vwce.total_value_eur).toBe(250);
    // Unrealized PnL = 250 - 200 = 50
    expect(vwce.unrealized_pnl_eur).toBe(50);
  });

  it('ensures historical portfolio equity begins at initial deposit and grows over time rather than pinning to latest value', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2024-04-02',
        time: '10:00',
        product: '',
        isin: '',
        description: 'iDEAL Deposit',
        amount: 10,
        value: 10,
        balance: 10,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'tx-1',
        isCashSweep: false,
      },
      {
        date: '2024-04-04',
        time: '11:00',
        product: 'AEGON LTD.',
        isin: 'BMG0112X1056',
        description: 'Koop 1 @ 5,75 EUR',
        amount: -5.75,
        value: -5.75,
        balance: 4.25,
        quantity: 1,
        price: 5.75,
        orderId: 'tx-2',
        rowHash: 'tx-2',
        isCashSweep: false,
      },
      {
        date: '2026-02-20',
        time: '12:00',
        product: '',
        isin: '',
        description: 'iDEAL Deposit',
        amount: 4000,
        value: 4000,
        balance: 4004.25,
        quantity: null,
        price: null,
        orderId: '',
        rowHash: 'tx-3',
        isCashSweep: false,
      },
      {
        date: '2026-02-20',
        time: '14:00',
        product: 'Vanguard FTSE All-World UCITS ETF',
        isin: 'IE00BK5BQT80',
        description: 'Koop 40 @ 100 EUR',
        amount: -4000,
        value: -4000,
        balance: 4.25,
        quantity: 40,
        price: 100,
        orderId: 'tx-4',
        rowHash: 'tx-4',
        isCashSweep: false,
      },
    ];

    const result = calculateDashboardFromTransactions(transactions, mockSettings);
    expect(result).not.toBeNull();
    if (!result) return;

    // Check earliest history point on 2024-04-02
    const firstDay = result.history.find((h) => h.date === '2024-04-02');
    expect(firstDay).toBeDefined();
    expect(firstDay?.invested_capital_eur).toBe(10);
    expect(firstDay?.total_equity_eur).toBe(10);
    expect(firstDay?.unrealized_pnl_eur).toBe(0);

    // After first stock purchase on 2024-04-04
    const purchaseDay = result.history.find((h) => h.date === '2024-04-04');
    expect(purchaseDay).toBeDefined();
    expect(purchaseDay?.invested_capital_eur).toBe(10);
    expect(purchaseDay?.total_equity_eur).toBeCloseTo(10, 1);

    // Latest day has the full ~4010 equity and invested capital
    const latestDay = result.history[result.history.length - 1];
    expect(latestDay.invested_capital_eur).toBe(4010);
    expect(latestDay.total_equity_eur).toBeGreaterThanOrEqual(4010);
  });

  it('populates asset breakdown for crypto and single-trade ETFs across multiple historical dates', () => {
    const transactions: IngestedTransaction[] = [
      {
        date: '2025-01-01',
        time: '10:00',
        product: '',
        isin: '',
        description: 'iDEAL Storting',
        amount: 2000,
        value: 2000,
        balance: 2000,
        quantity: null,
        price: null,
        orderId: 'dep-1',
        rowHash: 'dep-1',
        isCashSweep: false,
      },
      {
        date: '2025-01-15',
        time: '11:00',
        product: 'BITCOIN',
        isin: '',
        description: 'Koop 0.01 @ 50000 EUR',
        amount: -500,
        value: -500,
        balance: 1500,
        quantity: 0.01,
        price: 50000,
        orderId: 'tx-btc',
        rowHash: 'tx-btc',
        isCashSweep: false,
      },
      {
        date: '2025-02-01',
        time: '12:00',
        product: 'FUTURE OF DEFENCE UCITS - ACC ETF',
        isin: 'IE000OJ5TQP4',
        description: 'Koop 10 @ 18.00 EUR',
        amount: -180,
        value: -180,
        balance: 1320,
        quantity: 10,
        price: 18.0,
        orderId: 'tx-fod',
        rowHash: 'tx-fod',
        isCashSweep: false,
      },
    ];

    const result = calculateDashboardFromTransactions(transactions, mockSettings, {
      'BTC-EUR': 60000,
      'IE000OJ5TQP4': 19.5,
    });
    expect(result).not.toBeNull();
    if (!result) return;

    // Check intermediate date: both assets should exist in asset_breakdown
    const midPoint = result.history.find((h) => h.date === '2025-02-15');
    expect(midPoint).toBeDefined();
    expect(midPoint?.asset_breakdown?.['BTC-EUR']).toBeDefined();
    expect(midPoint?.asset_breakdown?.['BITCOIN']).toBeDefined();
    expect(midPoint?.asset_breakdown?.['IE000OJ5TQP4']).toBeDefined();
    expect(midPoint?.asset_breakdown?.['ASWC.DE']).toBeDefined();

    // Check final day: positive unrealized pnl for both
    const finalDay = result.history[result.history.length - 1];
    const btcSnap = finalDay.asset_breakdown?.['BTC-EUR'];
    const fodSnap = finalDay.asset_breakdown?.['ASWC.DE'];

    expect(btcSnap).toBeDefined();
    expect(btcSnap?.value_eur).toBeCloseTo(600, 0); // 0.01 * 60000
    expect(btcSnap?.pnl_eur).toBeGreaterThan(0);

    expect(fodSnap).toBeDefined();
    expect(fodSnap?.value_eur).toBeCloseTo(195, 0); // 10 * 19.50
    expect(fodSnap?.pnl_eur).toBeGreaterThan(0);
  });
});
