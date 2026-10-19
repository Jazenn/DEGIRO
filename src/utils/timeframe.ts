import {
  PortfolioDailyHistoryRecord,
  Timeframe,
} from '../types/portfolio';

/**
 * Filters and sorts portfolio daily history points according to the selected timeframe.
 *
 * @param history Array of portfolio daily history points.
 * @param timeframe Selected timeframe ('1M' | '3M' | '1Y' | 'ALL').
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

  const cutoffDate = new Date(baseDate.getTime());

  switch (timeframe) {
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
