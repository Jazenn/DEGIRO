/**
 * Live Price Service for DEGIRO Dashboard.
 * 
 * Fetches real-time market quotes from:
 * 1. TradeGate Exchange API (https://www.tradegate.de/refresh.php?isin=...) for European ETFs/Stocks.
 *    (TradeGate has Access-Control-Allow-Origin: * and is DEGIRO's primary execution venue).
 * 2. CoinGecko / Binance API for Bitcoin (BTC-EUR) and Ethereum (ETH-EUR).
 */

export function parsePriceString(val: unknown): number | null {
  if (typeof val === 'number') {
    return isFinite(val) && val > 0 ? val : null;
  }
  if (!val || typeof val !== 'string') return null;

  let clean = val.trim();
  if (clean.includes(',') && clean.includes('.')) {
    if (clean.lastIndexOf(',') > clean.lastIndexOf('.')) {
      // European 1.250,50
      clean = clean.replace(/\./g, '').replace(',', '.');
    } else {
      // US 1,250.50
      clean = clean.replace(/,/g, '');
    }
  } else if (clean.includes(',')) {
    clean = clean.replace(',', '.');
  }

  const num = parseFloat(clean);
  return !isNaN(num) && isFinite(num) && num > 0 ? num : null;
}

interface PriceCacheEntry {
  price: number;
  timestamp: number;
}

const priceCache: Record<string, PriceCacheEntry> = {};
const CACHE_TTL_MS = 60 * 1000; // 60 seconds

export function clearPriceCache(): void {
  for (const k of Object.keys(priceCache)) {
    delete priceCache[k];
  }
}

export async function fetchTradeGatePrice(
  isin: string,
  timeoutMs: number = 3000
): Promise<number | null> {
  const cleanIsin = isin.trim().toUpperCase();
  if (!cleanIsin || cleanIsin.length !== 12 || cleanIsin.startsWith('XFC')) {
    return null;
  }

  const cached = priceCache[cleanIsin];
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.price;
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const url = `https://www.tradegate.de/refresh.php?isin=${encodeURIComponent(cleanIsin)}`;
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (!response.ok) return null;
    const data = await response.json();
    const price = parsePriceString(data?.last);
    if (price && price > 0) {
      priceCache[cleanIsin] = { price, timestamp: Date.now() };
      return price;
    }
  } catch {
    // Network error or timeout - fallback to cached or null
  }

  return priceCache[cleanIsin]?.price ?? null;
}

export async function fetchCryptoPrices(
  timeoutMs: number = 3000
): Promise<{ btcEur: number | null; ethEur: number | null }> {
  const cachedBtc = priceCache['BTC-EUR'];
  const cachedEth = priceCache['ETH-EUR'];
  if (
    cachedBtc &&
    cachedEth &&
    Date.now() - cachedBtc.timestamp < CACHE_TTL_MS &&
    Date.now() - cachedEth.timestamp < CACHE_TTL_MS
  ) {
    return { btcEur: cachedBtc.price, ethEur: cachedEth.price };
  }

  let btcPrice: number | null = null;
  let ethPrice: number | null = null;

  // 1. Try CoinGecko
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const url =
      'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=eur';
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (response.ok) {
      const data = await response.json();
      if (data?.bitcoin?.eur) {
        btcPrice = parsePriceString(data.bitcoin.eur);
      }
      if (data?.ethereum?.eur) {
        ethPrice = parsePriceString(data.ethereum.eur);
      }
    }
  } catch {
    // CoinGecko failed or timed out
  }

  // 2. Fallback to Binance for missing crypto prices
  if (!btcPrice || !ethPrice) {
    try {
      const [btcRes, ethRes] = await Promise.allSettled([
        !btcPrice
          ? fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCEUR').then((r) =>
              r.json()
            )
          : null,
        !ethPrice
          ? fetch('https://api.binance.com/api/v3/ticker/price?symbol=ETHEUR').then((r) =>
              r.json()
            )
          : null,
      ]);

      if (btcRes.status === 'fulfilled' && btcRes.value?.price) {
        btcPrice = parsePriceString(btcRes.value.price) || btcPrice;
      }
      if (ethRes.status === 'fulfilled' && ethRes.value?.price) {
        ethPrice = parsePriceString(ethRes.value.price) || ethPrice;
      }
    } catch {
      // Fallback failed
    }
  }

  const now = Date.now();
  if (btcPrice && btcPrice > 0) {
    priceCache['BTC-EUR'] = { price: btcPrice, timestamp: now };
    priceCache['BITCOIN'] = { price: btcPrice, timestamp: now };
  }
  if (ethPrice && ethPrice > 0) {
    priceCache['ETH-EUR'] = { price: ethPrice, timestamp: now };
    priceCache['ETHEREUM'] = { price: ethPrice, timestamp: now };
  }

  return {
    btcEur: btcPrice || cachedBtc?.price || null,
    ethEur: ethPrice || cachedEth?.price || null,
  };
}

/**
 * Fetches live market prices for a list of holdings/assets.
 * Returns a map of symbol/isin/name -> current price in EUR.
 */
export async function fetchLivePricesForHoldings(
  holdings: Array<{ isin?: string | null; symbol?: string | null; name?: string | null }>
): Promise<Record<string, number>> {
  const result: Record<string, number> = {};

  const uniqueIsins = new Set<string>();
  let needsCrypto = false;

  for (const h of holdings) {
    const isin = (h.isin || '').trim().toUpperCase();
    const sym = (h.symbol || '').trim().toUpperCase();
    const name = (h.name || '').trim().toUpperCase();

    if (
      sym.includes('BTC') ||
      sym.includes('BITCOIN') ||
      name.includes('BITCOIN') ||
      sym.includes('ETH') ||
      sym.includes('ETHEREUM') ||
      name.includes('ETHEREUM')
    ) {
      needsCrypto = true;
    }

    if (isin && isin.length === 12 && !isin.startsWith('XFC')) {
      uniqueIsins.add(isin);
    }
  }

  const promises: Promise<void>[] = [];

  // Fetch crypto
  if (needsCrypto) {
    promises.push(
      fetchCryptoPrices().then(({ btcEur, ethEur }) => {
        if (btcEur && btcEur > 0) {
          result['BITCOIN'] = btcEur;
          result['BTC'] = btcEur;
          result['BTC-EUR'] = btcEur;
          result['Bitcoin'] = btcEur;
        }
        if (ethEur && ethEur > 0) {
          result['ETHEREUM'] = ethEur;
          result['ETH'] = ethEur;
          result['ETH-EUR'] = ethEur;
          result['Ethereum'] = ethEur;
        }
      })
    );
  }

  // Fetch stocks/ETFs from TradeGate
  for (const isin of uniqueIsins) {
    promises.push(
      fetchTradeGatePrice(isin).then((price) => {
        if (price && price > 0) {
          result[isin] = price;
        }
      })
    );
  }

  await Promise.allSettled(promises);
  return result;
}
