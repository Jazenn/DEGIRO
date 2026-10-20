import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  parsePriceString,
  fetchTradeGatePrice,
  fetchCryptoPrices,
  fetchLivePricesForHoldings,
  clearPriceCache,
} from './livePrices';

describe('livePrices service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    clearPriceCache();
  });

  describe('parsePriceString', () => {
    it('correctly parses numbers and strings with comma or dot decimals', () => {
      expect(parsePriceString(169.64)).toBe(169.64);
      expect(parsePriceString('169,60')).toBe(169.6);
      expect(parsePriceString('169.64')).toBe(169.64);
      expect(parsePriceString('1.250,50')).toBe(1250.5);
      expect(parsePriceString('1,250.50')).toBe(1250.5);
      expect(parsePriceString('72540.73')).toBe(72540.73);
      expect(parsePriceString('')).toBeNull();
      expect(parsePriceString(null)).toBeNull();
      expect(parsePriceString(undefined)).toBeNull();
      expect(parsePriceString('invalid')).toBeNull();
    });
  });

  describe('fetchTradeGatePrice', () => {
    it('returns parsed price when TradeGate responds with last price', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        json: async () => ({ last: '169,64' }),
      } as any);

      const price = await fetchTradeGatePrice('IE00BK5BQT80');
      expect(price).toBe(169.64);
    });

    it('returns null on invalid ISIN or fetch failure', async () => {
      expect(await fetchTradeGatePrice('INVALID')).toBeNull();

      vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network error'));
      expect(await fetchTradeGatePrice('IE00BK5BQT80')).toBeNull();
    });
  });

  describe('fetchCryptoPrices', () => {
    it('returns parsed BTC and ETH prices from CoinGecko', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          bitcoin: { eur: 72550 },
          ethereum: { eur: 2126.32 },
        }),
      } as any);

      const prices = await fetchCryptoPrices();
      expect(prices.btcEur).toBe(72550);
      expect(prices.ethEur).toBe(2126.32);
    });
  });

  describe('fetchLivePricesForHoldings', () => {
    it('fetches both TradeGate and Crypto prices for given holdings', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: any) => {
        const u = String(url);
        if (u.includes('tradegate')) {
          return {
            ok: true,
            json: async () => ({ last: '169,64' }),
          } as any;
        }
        if (u.includes('coingecko')) {
          return {
            ok: true,
            json: async () => ({
              bitcoin: { eur: 72550 },
              ethereum: { eur: 2126 },
            }),
          } as any;
        }
        return { ok: false } as any;
      });

      const holdings = [
        { isin: 'IE00BK5BQT80', symbol: 'IE00BK5BQT80', name: 'VWCE' },
        { isin: null, symbol: 'BITCOIN', name: 'BITCOIN' },
      ];

      const prices = await fetchLivePricesForHoldings(holdings);
      expect(prices['IE00BK5BQT80']).toBe(169.64);
      expect(prices['BITCOIN']).toBe(72550);
      expect(prices['BTC-EUR']).toBe(72550);
    });
  });
});
