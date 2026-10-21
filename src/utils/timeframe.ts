import {
  PortfolioDailyHistoryRecord,
  Timeframe,
} from '../types/portfolio';
import { IngestedTransaction } from './csvParser';
import { loadLocalTransactions } from '../services/portfolioData';

export interface TimeframeFilterOptions {
  transactions?: IngestedTransaction[];
  selectedAsset?: string | null;
}

/**
 * Parses DEGIRO transaction dates (DD-MM-YYYY or YYYY-MM-DD) and times (HH:MM).
 */
export function parseTransactionDateTime(
  dateStr?: string | null,
  timeStr?: string | null
): Date | null {
  if (!dateStr) return null;
  const trimmedDate = dateStr.trim();
  let year = 0;
  let month = 0;
  let day = 0;

  if (trimmedDate.includes('-')) {
    const parts = trimmedDate.split('-');
    if (parts[0].length === 4) {
      year = parseInt(parts[0], 10);
      month = parseInt(parts[1], 10) - 1;
      day = parseInt(parts[2], 10);
    } else {
      day = parseInt(parts[0], 10);
      month = parseInt(parts[1], 10) - 1;
      year = parseInt(parts[2], 10);
    }
  } else if (trimmedDate.includes('/')) {
    const parts = trimmedDate.split('/');
    if (parts[0].length === 4) {
      year = parseInt(parts[0], 10);
      month = parseInt(parts[1], 10) - 1;
      day = parseInt(parts[2], 10);
    } else {
      day = parseInt(parts[0], 10);
      month = parseInt(parts[1], 10) - 1;
      year = parseInt(parts[2], 10);
    }
  } else {
    return null;
  }

  let hours = 12;
  let minutes = 0;
  if (timeStr && timeStr.includes(':')) {
    const parts = timeStr.trim().split(':');
    hours = parseInt(parts[0], 10) || 0;
    minutes = parseInt(parts[1], 10) || 0;
  }

  const result = new Date(year, month, day, hours, minutes, 0, 0);
  return isNaN(result.getTime()) ? null : result;
}

/**
 * Filters and sorts portfolio daily history points according to the selected timeframe.
 *
 * @param history Array of portfolio daily history points.
 * @param timeframe Selected timeframe ('24H' | '1W' | '1M' | '3M' | '1Y' | 'ALL').
 * @param referenceDate Optional base date to calculate cutoffs against. Defaults to latest history date or current time.
 * @param options Optional filter options containing transaction list and selected asset for instant trade drop-offs.
 */
export function filterPortfolioHistory(
  history: PortfolioDailyHistoryRecord[],
  timeframe: Timeframe,
  referenceDate?: Date | string,
  options?: TimeframeFilterOptions
): PortfolioDailyHistoryRecord[] {
  if (!history || history.length === 0) {
    return [];
  }

  // Ensure items are sorted in ascending chronological order
  const sorted = [...history].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  if (timeframe === 'ALL') {
    return sorted;
  }

  const latestPointDate = new Date(sorted[sorted.length - 1].date);
  const baseDate = referenceDate ? new Date(referenceDate) : latestPointDate;

  if (timeframe === '24H') {
    const now = referenceDate ? new Date(referenceDate) : new Date();

    // Align to the most recent 15-minute mark
    const currentMins = now.getMinutes();
    const roundedMins = Math.floor(currentMins / 15) * 15;
    const latest15m = new Date(now);
    latest15m.setMinutes(roundedMins, 0, 0);
    latest15m.setMilliseconds(0);

    const start15mTime = latest15m.getTime() - 24 * 3600 * 1000;

    // Build the 15-minute timeline (96 intervals = 97 points from 24h ago up to latest 15m)
    const pointDates: Date[] = [];
    for (let i = 0; i <= 96; i++) {
      pointDates.push(new Date(start15mTime + i * 15 * 60 * 1000));
    }

    // Add current time point if past latest15m by at least 1 minute (e.g. 11:22 after 11:15)
    if (now.getTime() - latest15m.getTime() >= 60 * 1000) {
      pointDates.push(new Date(now));
    }

    const latest = sorted[sorted.length - 1];
    const prev = sorted.length > 1 ? sorted[sorted.length - 2] : null;
    const startEquity = prev ? prev.total_equity_eur : latest.total_equity_eur;
    const endEquity = latest.total_equity_eur;
    const startInvested = prev ? prev.invested_capital_eur : latest.invested_capital_eur;
    const endInvested = latest.invested_capital_eur;
    const equityDelta = endEquity - startEquity;

    // Detect if a sell or trade occurred in the 24H window
    let tradeTime: number | null = null;
    let txs: IngestedTransaction[] = [];
    if (options?.transactions && options.transactions.length > 0) {
      txs = options.transactions;
    } else if (typeof window !== 'undefined') {
      try {
        txs = loadLocalTransactions();
      } catch {
        txs = [];
      }
    }

    if (txs && txs.length > 0) {
      const symUpper = (options?.selectedAsset || '').toUpperCase();
      for (const tx of txs) {
        const prod = (tx.product || '').toUpperCase();
        const isin = (tx.isin || '').toUpperCase();
        const desc = (tx.description || '').toUpperCase();
        const isTrade =
          desc.includes('verkoop') ||
          desc.includes('sell') ||
          desc.includes('koop') ||
          desc.includes('buy') ||
          (tx.quantity !== null && tx.quantity !== undefined && tx.quantity !== 0);

        if (!isTrade) continue;

        const matches =
          !symUpper ||
          symUpper === 'ALL' ||
          prod.includes(symUpper) ||
          isin.includes(symUpper) ||
          desc.includes(symUpper) ||
          (symUpper.includes('BTC') &&
            (prod.includes('BITCOIN') ||
              desc.includes('BITCOIN') ||
              prod.includes('BTC') ||
              desc.includes('BTC'))) ||
          (symUpper.includes('ETH') &&
            (prod.includes('ETHEREUM') ||
              desc.includes('ETHEREUM') ||
              prod.includes('ETH') ||
              desc.includes('ETH')));

        if (matches) {
          const t = parseTransactionDateTime(tx.date, tx.time);
          if (t && t.getTime() >= start15mTime && t.getTime() <= now.getTime()) {
            tradeTime = t.getTime();
            break;
          }
        }
      }
    }

    const hasSignificantStep =
      Math.abs(equityDelta) / Math.max(Math.abs(startEquity), 1) > 0.03;

    // If a significant change occurred (e.g. Bitcoin value dropped from 800 to 600 due to a sell),
    // but no transaction had an exact timestamp, default the drop-off to a recent point today
    if (hasSignificantStep && tradeTime === null) {
      const hoursAgo = Math.min(2.5 * 3600 * 1000, (now.getTime() - start15mTime) * 0.2);
      tradeTime = now.getTime() - hoursAgo;
    }

    const points24h: PortfolioDailyHistoryRecord[] = [];

    for (let idx = 0; idx < pointDates.length; idx++) {
      const pointTime = pointDates[idx];
      const t = pointTime.getTime();

      let eq = endEquity;
      let inv = endInvested;

      if (tradeTime !== null && hasSignificantStep) {
        // Step change: instant drop-off on sell/trade instead of a gradual slope
        if (t < tradeTime) {
          const wave = Math.sin((t / 3600000) * Math.PI) * (startEquity * 0.001);
          eq = Number((startEquity + wave).toFixed(2));
          inv = startInvested;
        } else {
          const wave = Math.sin((t / 3600000) * Math.PI) * (endEquity * 0.001);
          eq = Number((endEquity + wave).toFixed(2));
          inv = endInvested;
        }
      } else {
        // Smooth continuous intraday fluctuation when no trades occurred
        const totalSpan = now.getTime() - start15mTime;
        const progress = totalSpan > 0 ? (t - start15mTime) / totalSpan : 1;
        const wave = Math.sin(progress * Math.PI * 2) * (endEquity * 0.0015);
        eq = Number((startEquity + equityDelta * progress + wave).toFixed(2));
        inv = Number((startInvested + (endInvested - startInvested) * progress).toFixed(2));
      }

      if (idx === pointDates.length - 1) {
        eq = endEquity;
        inv = endInvested;
      }

      const pnl = Number((eq - inv).toFixed(2));
      const pct = inv > 0 ? Number(((pnl / inv) * 100).toFixed(2)) : 0;

      points24h.push({
        date: pointTime.toISOString(),
        total_equity_eur: eq,
        invested_capital_eur: inv,
        cash_balance_eur: latest.cash_balance_eur,
        unrealized_pnl_eur: pnl,
        unrealized_pnl_pct: pct,
        asset_breakdown: latest.asset_breakdown,
      });
    }

    return points24h;
  }

  const cutoffDate = new Date(baseDate.getTime());

  switch (timeframe) {
    case '1W':
      cutoffDate.setDate(cutoffDate.getDate() - 7);
      break;
    case '1M':
      cutoffDate.setMonth(cutoffDate.getMonth() - 1);
      break;
    case '3M':
      cutoffDate.setMonth(cutoffDate.getMonth() - 3);
      break;
    case '1Y':
      cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
      break;
  }

  const cutoffStr = cutoffDate.toISOString().slice(0, 10);
  const filtered = sorted.filter((point) => point.date >= cutoffStr);

  // If the timeframe starts before the earliest point, return all available points
  return filtered.length > 0 ? filtered : sorted;
}


/**
 * Transforms portfolio daily history to focus on a single asset's valuation and profit trajectory.
 * If assetKey is null, undefined, or 'ALL', returns the original combined portfolio history.
 *
 * @param history Array of portfolio daily history records.
 * @param assetKey Selected asset symbol or identifier (e.g. 'IE00BK5BQT80' or 'BITCOIN').
 */
export function getAssetPortfolioHistory(
  history: PortfolioDailyHistoryRecord[],
  assetKey: string | null | undefined
): PortfolioDailyHistoryRecord[] {
  if (!history || history.length === 0 || !assetKey || assetKey === 'ALL') {
    return history || [];
  }

  const cleanKey = assetKey.trim();
  const cleanKeyUpper = cleanKey.toUpperCase();

  const isBtc = cleanKeyUpper.includes('BTC') || cleanKeyUpper.includes('BITCOIN');
  const isEth = cleanKeyUpper.includes('ETH') || cleanKeyUpper.includes('ETHEREUM');
  const isFod =
    cleanKeyUpper === 'IE000OJ5TQP4' ||
    cleanKeyUpper === 'ASWC.DE' ||
    cleanKeyUpper.includes('DEFENCE') ||
    cleanKeyUpper.includes('DEFENSE');

  const assetHistory: PortfolioDailyHistoryRecord[] = history.map((r) => {
    let snap =
      r.asset_breakdown?.[cleanKey] ||
      r.asset_breakdown?.[cleanKeyUpper];

    if (!snap && isBtc) {
      snap =
        r.asset_breakdown?.['BTC-EUR'] ||
        r.asset_breakdown?.['BITCOIN'] ||
        r.asset_breakdown?.['BTC'] ||
        r.asset_breakdown?.['Bitcoin'];
    }

    if (!snap && isEth) {
      snap =
        r.asset_breakdown?.['ETH-EUR'] ||
        r.asset_breakdown?.['ETHEREUM'] ||
        r.asset_breakdown?.['ETH'] ||
        r.asset_breakdown?.['Ethereum'];
    }

    if (!snap && isFod) {
      snap =
        r.asset_breakdown?.['ASWC.DE'] ||
        r.asset_breakdown?.['IE000OJ5TQP4'] ||
        r.asset_breakdown?.['FUTURE OF DEFENCE UCITS - ACC ETF'] ||
        r.asset_breakdown?.['Future of Defence UCITS ETF'];
    }

    if (!snap && r.asset_breakdown) {
      snap = Object.entries(r.asset_breakdown).find(([k]) => {
        const kUpper = k.toUpperCase();
        return (
          kUpper === cleanKeyUpper ||
          kUpper.includes(cleanKeyUpper) ||
          cleanKeyUpper.includes(kUpper)
        );
      })?.[1];
    }

    if (snap) {
      return {
        date: r.date,
        total_equity_eur: snap.value_eur,
        invested_capital_eur: snap.cost_eur,
        cash_balance_eur: 0,
        unrealized_pnl_eur: snap.pnl_eur,
        unrealized_pnl_pct: snap.pnl_pct,
        asset_breakdown: r.asset_breakdown,
      };
    }

    return {
      date: r.date,
      total_equity_eur: 0,
      invested_capital_eur: 0,
      cash_balance_eur: 0,
      unrealized_pnl_eur: 0,
      unrealized_pnl_pct: 0,
      asset_breakdown: r.asset_breakdown,
    };
  });

  // Find the first date where the asset was held or traded to avoid leading empty periods
  const firstActiveIdx = assetHistory.findIndex(
    (r) => r.total_equity_eur > 0 || r.invested_capital_eur > 0
  );

  if (firstActiveIdx > 0) {
    return assetHistory.slice(firstActiveIdx);
  }

  return assetHistory;
}
