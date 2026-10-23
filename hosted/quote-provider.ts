import type { Quote } from './valuation';
export interface QuoteMapping { symbol: string; provider: 'binance' | 'yahoo'; provider_symbol: string; evidence: string }
export async function fetchQuote(mapping: QuoteMapping, signal: AbortSignal, request: typeof fetch = fetch): Promise<Quote> {
  if (!mapping.evidence || !/^[A-Za-z0-9.^=:-]{1,80}$/.test(mapping.provider_symbol)) throw Error('unverified_quote_mapping');
  let price: string, observed: string;
  const url = mapping.provider === 'binance'
    ? 'https://api.binance.com/api/v3/aggTrades?limit=1&symbol=' + encodeURIComponent(mapping.provider_symbol)
    : 'https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(mapping.provider_symbol) + '?interval=1d&range=1d';
  const response = await request(url, { signal });
  if (!response.ok) throw Error('provider_unavailable');
  const body = await response.text();
  const result = JSON.parse(body);
  if (mapping.provider === 'binance') {
    if (!mapping.provider_symbol.endsWith('EUR') || !Array.isArray(result) || result.length !== 1 || typeof result[0].p !== 'string' || !Number.isFinite(result[0].T)) throw Error('provider_contract');
    price = result[0].p; observed = new Date(result[0].T).toISOString();
  } else {
    const meta = result.chart?.result?.[0]?.meta;
    // Preserve source numeric lexeme rather than round-trip its binary JSON number.
    const lexeme = body.match(/"regularMarketPrice"\s*:\s*(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/)?.[1];
    if (!meta || meta.currency !== 'EUR' || meta.symbol !== mapping.provider_symbol || !lexeme || !Number.isFinite(meta.regularMarketTime)) throw Error('provider_contract');
    price = lexeme; observed = new Date(meta.regularMarketTime * 1000).toISOString();
  }
  return { price_eur: price, observed_at: observed, retrieved_at: new Date().toISOString(), provider: mapping.provider,
    currency: 'EUR', adjustment_basis: 'unadjusted' };
}

