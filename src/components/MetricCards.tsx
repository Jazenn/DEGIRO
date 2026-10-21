import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  PiggyBank,
  Layers,
  Banknote,
  Coins,
} from 'lucide-react';
import { PortfolioMetrics } from '../types/portfolio';
import { formatEur, formatPct } from '../utils/metrics';

interface MetricCardsProps {
  metrics: PortfolioMetrics;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics }) => {
  const isPositive = metrics.totalGainLossEur >= 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
      {/* 1. Total Portfolio Value */}
      <div className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 transition shadow-sm relative overflow-hidden group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Total Portfolio Value
          </span>
          <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400">
            <Wallet className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
            {formatEur(metrics.totalPortfolioValue)}
          </h2>
          <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
            <Layers className="w-3.5 h-3.5 text-slate-500" />
            <span>
              {metrics.totalHoldingsCount}{' '}
              {metrics.totalHoldingsCount === 1 ? 'Holding' : 'Holdings'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Net Invested Capital */}
      <div className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 transition shadow-sm relative overflow-hidden group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Net Invested
          </span>
          <div className="p-2 rounded-xl bg-slate-800 text-slate-300">
            <PiggyBank className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
            {formatEur(metrics.netInvestedCapital)}
          </h2>
          <p className="mt-2 text-xs text-slate-400">Cumulative net deposits</p>
        </div>
      </div>

      {/* 3. Total Unrealized Gain/Loss */}
      <div className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 transition shadow-sm relative overflow-hidden group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Total Gain / Loss
          </span>
          <div
            className={`p-2 rounded-xl ${
              isPositive
                ? 'bg-emerald-500/10 text-emerald-400'
                : 'bg-rose-500/10 text-rose-400'
            }`}
          >
            {isPositive ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
          </div>
        </div>
        <div className="mt-3">
          <h2
            className={`text-2xl sm:text-3xl font-extrabold font-mono tracking-tight ${
              isPositive ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {isPositive && metrics.totalGainLossEur > 0
              ? `+${formatEur(metrics.totalGainLossEur)}`
              : formatEur(metrics.totalGainLossEur)}
          </h2>
          <div className="flex items-center gap-2 mt-2">
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-mono font-semibold ${
                isPositive
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-rose-500/15 text-rose-400'
              }`}
            >
              {formatPct(metrics.totalGainLossPct)}
            </span>
            <span className="text-xs text-slate-400">All-time return</span>
          </div>
        </div>
      </div>

      {/* 4. Free Cash Balance */}
      <div className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 transition shadow-sm relative overflow-hidden group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Free Cash
          </span>
          <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
            <Banknote className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
            {formatEur(metrics.freeCashBalance)}
          </h2>
          <p className="mt-2 text-xs text-slate-400">Available dry powder</p>
        </div>
      </div>

      {/* 5. Dividends Paid Out */}
      <div
        data-testid="metric-dividends-card"
        className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 transition shadow-sm relative overflow-hidden group"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Dividends Paid
          </span>
          <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
            <Coins className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-teal-400 tracking-tight">
            {metrics.totalDividendsEur !== undefined && metrics.totalDividendsEur > 0
              ? `+${formatEur(metrics.totalDividendsEur)}`
              : formatEur(metrics.totalDividendsEur ?? 0)}
          </h2>
          <p className="mt-2 text-xs text-slate-400">Cumulative payouts</p>
        </div>
      </div>
    </div>
  );
};
