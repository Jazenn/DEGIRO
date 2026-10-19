import React, { useState, useMemo } from 'react';
import { CurrentAssetHoldingRecord } from '../types/portfolio';
import { calculateRebalancePlan, RebalanceItem } from '../utils/rebalance';
import { formatEur } from '../utils/metrics';
import {
  SlidersHorizontal,
  Sparkles,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';

export interface RebalanceCockpitProps {
  holdings: CurrentAssetHoldingRecord[];
  totalPortfolioValue: number;
  initialDeposit?: number;
}

const PRESETS = [250, 500, 800, 1000, 1500];

export const RebalanceCockpit: React.FC<RebalanceCockpitProps> = ({
  holdings,
  totalPortfolioValue,
  initialDeposit = 800,
}) => {
  const [depositAmount, setDepositAmount] = useState<number>(initialDeposit);

  const plan = useMemo(() => {
    return calculateRebalancePlan(depositAmount, holdings, totalPortfolioValue);
  }, [depositAmount, holdings, totalPortfolioValue]);

  // Identify highest allocation among underweight assets for "Primary Fill" tag
  const highestBuySymbol = useMemo(() => {
    if (!plan.items || plan.items.length === 0) return null;
    let maxBuy = 0;
    let topSym: string | null = null;
    for (const item of plan.items) {
      if (item.recommendedBuyEur > maxBuy) {
        maxBuy = item.recommendedBuyEur;
        topSym = item.symbol;
      }
    }
    return topSym;
  }, [plan]);

  const handleDepositChange = (value: number) => {
    setDepositAmount(Math.max(0, value));
  };

  const getPriorityBadge = (item: RebalanceItem) => {
    if (item.recommendedBuyEur > 0) {
      if (item.symbol === highestBuySymbol) {
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-sky-500/15 text-sky-400 border border-sky-500/30 flex items-center gap-1 shadow-sm">
            <Sparkles className="w-3 h-3" />
            Primary Fill
          </span>
        );
      }
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
          Secondary Fill
        </span>
      );
    }

    if (item.status === 'overweight') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          Overweight
        </span>
      );
    }

    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700/60">
        On Target
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Interactive Simulator Card */}
      <div className="bg-gradient-to-r from-sky-950/40 via-slate-900 to-slate-900 border border-sky-800/40 rounded-2xl p-6 sm:p-7 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 text-sky-400 text-xs font-bold uppercase tracking-wider mb-2">
              <SlidersHorizontal className="w-4 h-4" />
              Monthly Inflow Rebalancing Simulator
            </div>
            <h2 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
              Interactive Rebalancing Cockpit
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 leading-relaxed">
              Move the slider or type an amount. The engine dynamically calculates the exact buy
              distribution to bring underweight assets back to their targets without selling any
              holdings or incurring capital gains tax.
            </p>
          </div>

          {/* Quick Presets */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-xs text-slate-500 font-mono hidden sm:inline">Presets:</span>
            {PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => handleDepositChange(p)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-semibold transition border ${
                  depositAmount === p
                    ? 'bg-sky-600 text-white border-sky-500 shadow-sm'
                    : 'bg-slate-950 hover:bg-slate-800 text-slate-300 border-slate-800 hover:border-slate-700'
                }`}
              >
                {formatEur(p).replace('.00', '')}
              </button>
            ))}
          </div>
        </div>

        {/* Slider & Input Row */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6 mt-6 pt-5 border-t border-slate-800/80">
          <div className="relative flex-1">
            <input
              type="range"
              data-testid="deposit-slider"
              min="100"
              max="2500"
              step="50"
              value={depositAmount}
              onChange={(e) => handleDepositChange(parseFloat(e.target.value) || 0)}
              aria-label="Planned monthly deposit slider"
              className="w-full h-2.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
            />
            <div className="flex justify-between text-[11px] font-mono text-slate-500 mt-2">
              <span>€100</span>
              <span>€1,000</span>
              <span>€2,500</span>
            </div>
          </div>

          <div className="flex items-center gap-2.5 self-start sm:self-center">
            <span className="text-sm font-mono text-slate-400 font-medium">€</span>
            <input
              type="number"
              data-testid="deposit-number-input"
              min="0"
              step="50"
              value={depositAmount}
              onChange={(e) => handleDepositChange(parseFloat(e.target.value) || 0)}
              aria-label="Planned deposit number input"
              className="w-32 px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white font-mono font-bold text-base focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 shadow-inner"
            />
          </div>
        </div>
      </div>

      {/* Target Distribution Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <span>Target Distribution for</span>
          <span data-testid="current-deposit-label" className="text-white font-mono font-extrabold text-base">
            {formatEur(depositAmount)}
          </span>
        </h3>

        <div className="flex items-center gap-3">
          <span
            data-testid="post-rebalance-drift"
            className="text-xs font-mono font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-3 py-1 rounded-full flex items-center gap-1.5 shadow-sm"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Post-rebalance Drift: {plan.postRebalanceMaxDriftPct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Recommended Order Cards Grid */}
      {plan.items.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center text-slate-500 text-sm font-mono">
          No assets available to rebalance.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plan.items.map((item) => {
            const hasBuy = item.recommendedBuyEur > 0;

            return (
              <div
                key={item.symbol}
                data-testid={`rebalance-card-${item.symbol}`}
                className={`rounded-2xl p-5 border flex flex-col justify-between transition-all duration-150 ${
                  hasBuy
                    ? 'bg-slate-900/90 border-slate-800 hover:border-slate-700 shadow-lg shadow-black/20'
                    : 'bg-slate-900/50 border-slate-800/60 opacity-80'
                }`}
              >
                <div>
                  {/* Card Header: Symbol, Name, Priority Badge */}
                  <div className="flex justify-between items-start gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-slate-400">
                          {item.symbol}
                        </span>
                        {item.isin && (
                          <span className="text-[10px] font-mono text-slate-500 truncate max-w-[100px]">
                            {item.isin}
                          </span>
                        )}
                      </div>
                      <h4 className="font-bold text-white text-base truncate mt-0.5" title={item.name}>
                        {item.name}
                      </h4>
                    </div>

                    <div className="flex-shrink-0">
                      {getPriorityBadge(item)}
                    </div>
                  </div>

                  {/* Purchase Amount & Share Quantity */}
                  <div className="mt-4 pt-3 border-t border-slate-800/80">
                    <div className="flex items-baseline gap-2">
                      <span
                        className={`text-2xl sm:text-3xl font-extrabold font-mono tracking-tight ${
                          hasBuy ? 'text-sky-400' : 'text-slate-500'
                        }`}
                      >
                        {formatEur(item.recommendedBuyEur)}
                      </span>
                    </div>

                    <p className="text-xs font-mono text-slate-400 mt-1">
                      {hasBuy ? (
                        <>
                          Approx.{' '}
                          <span className="text-slate-200 font-semibold">
                            {item.estimatedShares.toFixed(1)}
                          </span>{' '}
                          shares @ {formatEur(item.currentPriceEur)}
                        </>
                      ) : (
                        'Overweight / on target: no purchase needed'
                      )}
                    </p>
                  </div>
                </div>

                {/* Progress / Drift Visualizer */}
                <div className="mt-5 pt-3 border-t border-slate-800/60 space-y-2">
                  <div className="flex justify-between items-center text-[11px] font-mono">
                    <span className="text-slate-400">
                      Current: <strong className="text-white">{item.actualPct.toFixed(1)}%</strong>
                    </span>
                    <span className="flex items-center gap-1 text-slate-500">
                      <ArrowRight className="w-3 h-3 text-slate-600" />
                      Target: <strong className="text-slate-300">{item.targetPct.toFixed(1)}%</strong>
                    </span>
                    <span className="text-sky-400 font-semibold">
                      New: {item.projectedPct.toFixed(1)}%
                    </span>
                  </div>

                  {/* Progress Track */}
                  <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden flex border border-slate-800">
                    <div
                      className="bg-slate-600 transition-all duration-300"
                      style={{ width: `${Math.min(100, item.actualPct)}%` }}
                      title={`Current ${item.actualPct.toFixed(1)}%`}
                    />
                    {hasBuy && (
                      <div
                        className="bg-sky-500 transition-all duration-300 animate-pulse"
                        style={{
                          width: `${Math.max(0, Math.min(100 - item.actualPct, item.projectedPct - item.actualPct))}%`,
                        }}
                        title={`Projected Inflow +${(item.projectedPct - item.actualPct).toFixed(1)}%`}
                      />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default RebalanceCockpit;
