import { describe, it, expect } from 'vitest';
import { parseDegiroCsv, CsvParseResult, computeMd5Hash } from './csvParser';

describe('parseDegiroCsv', () => {
  it('computes standard RFC 1321 MD5 hashes matching known test vectors', () => {
    expect(computeMd5Hash('')).toBe('d41d8cd98f00b204e9800998ecf8427e');
    expect(computeMd5Hash('a')).toBe('0cc175b9c0f1b6a831c399e269772661');
    expect(computeMd5Hash('abc')).toBe('900150983cd24fb0d6963f7d28e17f72');
    expect(computeMd5Hash('message digest')).toBe('f96b697d7cb7938d525a2f31aaf161d0');
  });

  it('parses valid Dutch Transactions CSV correctly and generates 32-character MD5 row_hash', () => {
    const csvContent = `Datum;Tijd;Product;ISIN;Aantal;Koers;Waarde;Order Id
2026-01-15;10:30;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;10;120.50;-1205.00;ORD-001
2026-01-20;14:15;iShares MSCI World ex-USA;IE0006WW1TQ4;5;55.00;-275.00;ORD-002
`;

    const result: CsvParseResult = parseDegiroCsv(csvContent);

    expect(result.success).toBe(true);
    expect(result.rowsProcessed).toBe(2);
    expect(result.newRows).toBe(2);
    expect(result.duplicatesSkipped).toBe(0);
    expect(result.transactions.length).toBe(2);
    expect(result.transactions[0].product).toBe('Vanguard FTSE All-World UCITS ETF');
    expect(result.transactions[0].quantity).toBe(10);
    expect(result.transactions[0].price).toBe(120.5);
    expect(result.transactions[0].value).toBe(-1205.0);
    expect(result.transactions[0].rowHash).toHaveLength(32);
    expect(result.transactions[0].rowHash).toMatch(/^[0-9a-f]{32}$/);
    expect(result.transactions[1].rowHash).toHaveLength(32);
    expect(result.transactions[1].rowHash).toMatch(/^[0-9a-f]{32}$/);
  });

  it('parses valid English Transactions CSV with comma delimiter', () => {
    const csvContent = `Date,Time,Product,ISIN,Quantity,Price,Value,Order Id
2026-02-10,09:45,Bitcoin,XFC000A2YY6Q,0.05,65000.00,-3250.00,ORD-003
2026-02-15,11:00,Clean Energy & Technology ETF,IE000OJ5TQP4,20,25.00,-500.00,ORD-004
`;

    const result = parseDegiroCsv(csvContent);

    expect(result.success).toBe(true);
    expect(result.rowsProcessed).toBe(2);
    expect(result.newRows).toBe(2);
    expect(result.transactions[0].product).toBe('Bitcoin');
    expect(result.transactions[0].quantity).toBe(0.05);
  });

  it('identifies and skips duplicate rows based on deterministic row signature', () => {
    const csvContent = `Datum;Tijd;Product;ISIN;Aantal;Koers;Waarde;Order Id
2026-01-15;10:30;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;10;120.50;-1205.00;ORD-001
2026-01-15;10:30;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;10;120.50;-1205.00;ORD-001
2026-01-20;14:15;iShares MSCI World ex-USA;IE0006WW1TQ4;5;55.00;-275.00;ORD-002
`;

    const result = parseDegiroCsv(csvContent);

    expect(result.success).toBe(true);
    expect(result.rowsProcessed).toBe(3);
    expect(result.newRows).toBe(2);
    expect(result.duplicatesSkipped).toBe(1);
    expect(result.transactions.length).toBe(2);
  });

  it('handles existing hashes passed to deduplicate against previously imported data', () => {
    const csvContent = `Date,Time,Product,ISIN,Quantity,Price,Value,Order Id
2026-01-15,10:30,Vanguard FTSE All-World UCITS ETF,IE00BK5BQT80,10,120.50,-1205.00,ORD-001
`;
    // Parse first time to get hash
    const firstResult = parseDegiroCsv(csvContent);
    const existingHashes = [firstResult.transactions[0].rowHash];

    // Parse again providing existingHashes
    const secondResult = parseDegiroCsv(csvContent, { existingHashes });

    expect(secondResult.rowsProcessed).toBe(1);
    expect(secondResult.newRows).toBe(0);
    expect(secondResult.duplicatesSkipped).toBe(1);
  });

  it('handles Dutch Account.csv format with Omschrijving and Mutatie', () => {
    const csvContent = `Datum;Tijd;Product;ISIN;Omschrijving;Mutatie;Saldo;Order Id
2026-03-01;08:00;;;iDEAL Storting;500.00;500.00;
2026-03-02;11:20;Vanguard FTSE All-World;IE00BK5BQT80;Koop 4 @ 120.00;-480.00;20.00;ORD-005
`;

    const result = parseDegiroCsv(csvContent);

    expect(result.success).toBe(true);
    expect(result.rowsProcessed).toBe(2);
    expect(result.newRows).toBe(2);
  });

  it('handles Dutch Account.csv with currency column shifting and extracts trade from description', () => {
    const csvContent = `Datum;Tijd;Valutadatum;Product;ISIN;Omschrijving;FX;;Mutatie;;Saldo;;Order Id
01-01-2024;09:00;01-01-2024;DEGIRO;NLFLATEXACNT;iDEAL Storting;;;EUR;5000,00;EUR;5000,00;;
02-01-2024;10:00;02-01-2024;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;Koop 30 @ 100,00 EUR;;;EUR;-3000,00;EUR;2000,00;;ORD-1
03-01-2024;11:00;03-01-2024;Bitcoin;XFC000A2YY6Q;Koop 0,02 @ 50.000,00 EUR;;;EUR;-1000,00;EUR;1000,00;;ORD-2
`;

    const result = parseDegiroCsv(csvContent);

    expect(result.success).toBe(true);
    expect(result.rowsProcessed).toBe(3);
    expect(result.newRows).toBe(3);

    // Row 0: Storting
    expect(result.transactions[0].date).toBe('2024-01-01');
    expect(result.transactions[0].amount).toBe(5000.0);
    expect(result.transactions[0].balance).toBe(5000.0);

    // Row 1: VWCE Buy
    expect(result.transactions[1].date).toBe('2024-01-02');
    expect(result.transactions[1].quantity).toBe(30);
    expect(result.transactions[1].price).toBe(100.0);
    expect(result.transactions[1].amount).toBe(-3000.0);
    expect(result.transactions[1].balance).toBe(2000.0);

    // Row 2: BTC Buy
    expect(result.transactions[2].date).toBe('2024-01-03');
    expect(result.transactions[2].quantity).toBe(0.02);
    expect(result.transactions[2].price).toBe(50000.0);
    expect(result.transactions[2].amount).toBe(-1000.0);
    expect(result.transactions[2].balance).toBe(1000.0);
  });

  it('normalizes European DD-MM-YYYY dates correctly', () => {
    const csvContent = `Datum;Tijd;Product;ISIN;Omschrijving;Mutatie;Saldo;Order Id
15-08-2024;09:00;DEGIRO;NLFLATEXACNT;Storting;500.00;500.00;
`;
    const result = parseDegiroCsv(csvContent);
    expect(result.success).toBe(true);
    expect(result.transactions[0].date).toBe('2024-08-15');
  });

  it('returns descriptive error when CSV format is invalid or missing headers', () => {
    const invalidCsv = `Col1,Col2,Col3
val1,val2,val3
`;

    const result = parseDegiroCsv(invalidCsv);

    expect(result.success).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors[0]).toContain('Unsupported DEGIRO CSV format');
  });

  it('handles empty input gracefully', () => {
    const result = parseDegiroCsv('');

    expect(result.success).toBe(false);
    expect(result.rowsProcessed).toBe(0);
    expect(result.newRows).toBe(0);
  });
});
