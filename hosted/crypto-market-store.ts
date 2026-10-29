import { neon } from '@neondatabase/serverless';
import { validateTemplates, defaultPercentiles } from './crypto-levels';
import { preparedLevels } from './prepared-crypto-market';
export interface MarketSeries { coin: string; version: string; prepared_summary?: unknown; attempted_at: string; diagnostics: string[] }
export interface CryptoMarketReader { read(coin: string): Promise<MarketSeries | null> }
export function neonCryptoMarketReader(url: string): CryptoMarketReader {
  const sql = neon(url);
  return { async read(coin) {
    const rows = await sql.query(`SELECT coin, version, prepared_summary,
      to_char(attempted_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS attempted_at,
      diagnostics FROM hosted_crypto_market_history WHERE coin=$1`, [coin]);
    return (rows[0] as MarketSeries | undefined) || null;
  } };
}
export async function previewCryptoLevels(input: unknown, reader: CryptoMarketReader, now = new Date().toISOString()) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw Error('invalid_request');
  const value = input as Record<string, unknown>;
  if (!['BTC-EUR', 'ETH-EUR'].includes(String(value.coin))) throw Error('invalid_coin');
  const templates = validateTemplates(value.templates === undefined ? defaultPercentiles : value.templates);
  const series = await reader.read(String(value.coin));
  if (value.market_version !== undefined && value.market_version !== (series?.version || null))
    return { state: 'stale', reason: 'market_history_changed' };
  return { ...await preparedLevels(String(value.coin), series?.version, series && series.coin === value.coin ? series.prepared_summary : null, now, templates),
    market_version: series?.version || null, attempted_at: series?.attempted_at || null,
    provider_diagnostics: series?.diagnostics || ['market_history_not_published'] };
}
