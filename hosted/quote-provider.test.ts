import { expect, test } from 'vitest';
import { fetchQuote } from './quote-provider';

test('explicit Kraken EUR mappings retain exact prices and actual trade timestamps', async () => {
  const calls: string[] = [];
  for (const [symbol, pair] of [['BTC-EUR', 'XXBTZEUR'], ['ETH-EUR', 'XETHZEUR']]) {
    const quote = await fetchQuote({ symbol, provider: 'kraken', provider_symbol: pair, evidence: 'invented holding; reviewed public EUR pair' }, new AbortController().signal,
      async url => {
        calls.push(String(url));
        return Response.json({ error: [], result: { [pair]: [['100000.0000000000000001', '0.01', 1792749600.125, 'b', 'm', '', 1]], last: '1792749600999999999' } });
      });
    expect(quote.price_eur).toBe('100000.0000000000000001');
    expect(quote.observed_at).toBe('2026-10-23T10:00:00.125Z');
    expect(quote.provider).toBe('kraken');
    expect(quote.currency).toBe('EUR');
  }
  expect(calls).toEqual(['https://api.kraken.com/0/public/Trades?count=1&pair=XXBTZEUR', 'https://api.kraken.com/0/public/Trades?count=1&pair=XETHZEUR']);
});

test('Kraken rejects mismatched public identities and malformed trade observations without inference', async () => {
  let requests = 0;
  const signal = new AbortController().signal;
  await expect(fetchQuote({ symbol: 'BTC-EUR', provider: 'kraken', provider_symbol: 'XETHZEUR', evidence: 'incorrect pair' }, signal,
    async () => { requests++; return Response.json({}); })).rejects.toThrow('unverified_quote_mapping');
  expect(requests).toBe(0);
  const mapping = { symbol: 'BTC-EUR', provider: 'kraken' as const, provider_symbol: 'XXBTZEUR', evidence: 'invented reviewed mapping' };
  const valid = { error: [] as string[], result: { XXBTZEUR: [['100', '0.01', 1792749600, 'b', 'm', '', 1] as unknown[]], last: '1792749600123456789' } };
  for (const change of [
    (value: any) => { value.error = ['private provider error detail']; },
    (value: any) => { value.result = { XETHZEUR: value.result.XXBTZEUR, last: value.result.last }; },
    (value: any) => { value.result.XXBTZEUR[0][0] = 100; },
    (value: any) => { value.result.XXBTZEUR[0][0] = '0.000'; },
    (value: any) => { value.result.XXBTZEUR[0][2] = null; },
    (value: any) => { value.result.XXBTZEUR = []; },
    (value: any) => { value.result.XXBTZEUR.push([...value.result.XXBTZEUR[0]]); },
  ]) {
    const value = structuredClone(valid); change(value);
    await expect(fetchQuote(mapping, signal, async () => Response.json(value))).rejects.toThrow('provider_contract');
  }
});
