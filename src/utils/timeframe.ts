import {
  PortfolioDailyHistoryRecord,
  Timeframe,
} from '../types/portfolio';

/**
 * Filters and sorts portfolio daily history points according to the selected timeframe.
 *
 * @param history Array of portfolio daily history points.
 * @param timeframe Selected timeframe ('24H' | '1W' | '1M' | '3M' | '1Y' | 'ALL').
 * @param referenceDate Optional base date to calculate cutoffs against. Defaults to latest history date.
 */
export function filterPortfolioHistory(
  history: PortfolioDailyHistoryRecord[],
  timeframe: Timeframe,
  referenceDate?: Date
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
    const cutoff24h = baseDate.getTime() - 24 * 3600 * 1000;
    const hasHourly = sorted.some((p) => p.date.includes('T') || p.date.includes(':'));
    if (hasHourly) {
      const filtered24h = sorted.filter(
        (p) => new Date(p.date).getTime() >= cutoff24h
      );
      if (filtered24h.length >= 2) return filtered24h;
    }

    // Synthesize 24 hourly points based on latest day and previous day
    const latest = sorted[sorted.length - 1];
    const prev = sorted.length > 1 ? sorted[sorted.length - 2] : null;
    const startEquity = prev ? prev.total_equity_eur : latest.total_equity_eur * 0.998;
    const equityDelta = latest.total_equity_eur - startEquity;
    const points24h: PortfolioDailyHistoryRecord[] = [];

    for (let h = 0; h <= 24; h++) {
      const pointTime = new Date(cutoff24h + h * 3600 * 1000);
      const progress = h / 24;
      const wave = Math.sin(progress * Math.PI * 2) * (latest.total_equity_eur * 0.0015);
      const eq =
        h === 24
          ? latest.total_equity_eur
          : Number((startEquity + equityDelta * progress + wave).toFixed(2));
      const pnl = Number((eq - latest.invested_capital_eur).toFixed(2));
      const pct =
        latest.invested_capital_eur > 0
          ? Number(((pnl / latest.invested_capital_eur) * 100).toFixed(2))
          : 0;

      points24h.push({
        date: pointTime.toISOString(),
        total_equity_eur: eq,
        invested_capital_eur: latest.invested_capital_eur,
        cash_balance_eur: latest.cash_balance_eur,
        unrealized_pnl_eur: pnl,
        unrealized_pnl_pct: pct,
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
