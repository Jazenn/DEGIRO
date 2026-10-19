import React, { useState, useMemo } from 'react';
import { CurrentAssetHoldingRecord } from '../types/portfolio';
import { formatEur, formatPct } from '../utils/metrics';
import { PieChart, TrendingUp, TrendingDown, CheckCircle2 } from 'lucide-react';

export interface AllocationDonutProps {
  holdings: CurrentAssetHoldingRecord[];
  totalPortfolioValue: number;
}

const PALETTE = [
  '#0284c7', // Sky 600
  '#10b981', // Emerald 500
  '#f59e0b', // Amber 500
  '#6366f1', // Indigo 500
  '#a855f7', // Purple 500
  '#f43f5e', // Rose 500
  '#14b8a6', // Teal 500
  '#eab308', // Yellow 500
  '#64748b', // Slate 500
];

interface SliceData {
  holding: CurrentAssetHoldingRecord;
  color: string;
  startAngle: number;
  endAngle: number;
  pathD: string;
  hoverPathD: string;
  percentage: number;
}

export const AllocationDonut: React.FC<AllocationDonutProps> = ({
  holdings,
  totalPortfolioValue,
}) => {
  const [hoveredSymbol, setHoveredSymbol] = useState<string | null>(null);

  const sortedHoldings = useMemo(() => {
    return [...holdings].sort((a, b) => (b.total_value_eur || 0) - (a.total_value_eur || 0));
  }, [holdings]);

  const totalValue = useMemo(() => {
    const sum = holdings.reduce((acc, h) => acc + (Number(h.total_value_eur) || 0), 0);
    return sum > 0 ? sum : totalPortfolioValue;
  }, [holdings, totalPortfolioValue]);

  // SVG parameters
  const size = 300;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = 115;
  const innerR = 80;
  const hoverOuterR = 122;

  const slices: SliceData[] = useMemo(() => {
    if (!sortedHoldings || sortedHoldings.length === 0 || totalValue <= 0) {
      return [];
    }

    let currentAngle = -Math.PI / 2; // Start at 12 o'clock

    return sortedHoldings.map((h, idx) => {
      const color = PALETTE[idx % PALETTE.length];
      const sliceVal = Number(h.total_value_eur) || 0;
      const proportion = sliceVal / totalValue;
      const angleSpan = proportion * 2 * Math.PI;

      const startAngle = currentAngle;
      const endAngle = currentAngle + angleSpan;
      currentAngle = endAngle;

      // Arc helper
      const buildArc = (R: number, r: number) => {
        // If single slice taking up practically 100%
        if (angleSpan >= 2 * Math.PI - 0.001) {
          return [
            `M ${cx} ${cy - R}`,
            `A ${R} ${R} 0 1 1 ${cx - 0.01} ${cy - R}`,
            `L ${cx - 0.01} ${cy - r}`,
            `A ${r} ${r} 0 1 0 ${cx} ${cy - r}`,
            'Z',
          ].join(' ');
        }

        const x1 = cx + R * Math.cos(startAngle);
        const y1 = cy + R * Math.sin(startAngle);
        const x2 = cx + R * Math.cos(endAngle);
        const y2 = cy + R * Math.sin(endAngle);

        const x3 = cx + r * Math.cos(endAngle);
        const y3 = cy + r * Math.sin(endAngle);
        const x4 = cx + r * Math.cos(startAngle);
        const y4 = cy + r * Math.sin(startAngle);

        const largeArc = angleSpan > Math.PI ? 1 : 0;

        return [
          `M ${x1} ${y1}`,
          `A ${R} ${R} 0 ${largeArc} 1 ${x2} ${y2}`,
          `L ${x3} ${y3}`,
          `A ${r} ${r} 0 ${largeArc} 0 ${x4} ${y4}`,
          'Z',
        ].join(' ');
      };

      return {
        holding: h,
        color,
        startAngle,
        endAngle,
        pathD: buildArc(outerR, innerR),
        hoverPathD: buildArc(hoverOuterR, innerR),
        percentage: Number(h.actual_pct) || proportion * 100,
      };
    });
  }, [sortedHoldings, totalValue]);

  const activeHolding = useMemo(() => {
    if (!hoveredSymbol) return null;
    return holdings.find((h) => h.symbol === hoveredSymbol) || null;
  }, [hoveredSymbol, holdings]);

  const getDriftBadge = (drift: number) => {
    if (drift < -0.05) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <TrendingDown className="w-3 h-3" />
          {drift.toFixed(1)}% Underweight
        </span>
      );
    }
    if (drift > 0.05) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <TrendingUp className="w-3 h-3" />
          +{drift.toFixed(1)}% Overweight
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <CheckCircle2 className="w-3 h-3" />
        0.0% On Target
      </span>
    );
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xl">
      {/* Card Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <PieChart className="w-4 h-4" />
          </div>
          <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
            Asset Allocation
          </h2>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800/90 text-slate-300 font-mono font-medium border border-slate-700/60">
          {holdings.length} Assets
        </span>
      </div>

      {holdings.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm font-mono">
          No assets currently in portfolio.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          {/* Interactive Donut Graphic */}
          <div className="lg:col-span-5 flex flex-col items-center justify-center relative">
            <div className="relative w-[280px] h-[280px] sm:w-[300px] sm:h-[300px]">
              <svg
                viewBox={`0 0 ${size} ${size}`}
                className="w-full h-full transform -rotate-90 transition-transform duration-300"
                aria-label="Asset Allocation Donut Chart"
              >
                {slices.map((slice) => {
                  const isHovered = hoveredSymbol === slice.holding.symbol;
                  return (
                    <path
                      key={slice.holding.symbol}
                      d={isHovered ? slice.hoverPathD : slice.pathD}
                      fill={slice.color}
                      data-slice-symbol={slice.holding.symbol}
                      className="cursor-pointer transition-all duration-200 stroke-slate-950 stroke-[2.5]"
                      onMouseEnter={() => setHoveredSymbol(slice.holding.symbol)}
                      onMouseLeave={() => setHoveredSymbol(null)}
                      style={{
                        filter: isHovered
                          ? 'drop-shadow(0px 0px 8px rgba(255,255,255,0.3))'
                          : 'none',
                      }}
                    />
                  );
                })}
              </svg>

              {/* Donut Center Display */}
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none px-6">
                {activeHolding ? (
                  <>
                    <span
                      data-testid="donut-center-symbol"
                      className="text-xs font-mono font-bold text-sky-400 truncate max-w-[140px]"
                    >
                      {activeHolding.symbol}
                    </span>
                    <span
                      data-testid="donut-center-pct"
                      className="text-2xl font-black font-mono text-white mt-0.5 tracking-tight"
                    >
                      {formatPct(activeHolding.actual_pct, false)}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400 mt-0.5">
                      Target {formatPct(activeHolding.target_pct, false)}
                    </span>
                  </>
                ) : (
                  <>
                    <span
                      data-testid="donut-center-title"
                      className="text-[11px] uppercase font-bold tracking-wider text-slate-400"
                    >
                      Portfolio Value
                    </span>
                    <span className="text-xl sm:text-2xl font-black font-mono text-white mt-0.5 tracking-tight">
                      {formatEur(totalValue)}
                    </span>
                    <span className="text-[11px] font-mono text-slate-500 mt-0.5">
                      Hover asset to inspect
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Asset Legends & Drift Table */}
          <div className="lg:col-span-7 space-y-2.5">
            {slices.map((slice) => {
              const h = slice.holding;
              const isHovered = hoveredSymbol === h.symbol;
              const drift = typeof h.drift_pct === 'number' ? h.drift_pct : (h.actual_pct - h.target_pct);

              return (
                <div
                  key={h.symbol}
                  onMouseEnter={() => setHoveredSymbol(h.symbol)}
                  onMouseLeave={() => setHoveredSymbol(null)}
                  className={`p-3 rounded-xl border transition-all duration-150 cursor-pointer ${
                    isHovered
                      ? 'bg-slate-800/90 border-slate-600 shadow-md translate-x-1'
                      : 'bg-slate-950/50 border-slate-800/80 hover:bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    {/* Left: Color dot + Symbol + Name */}
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span
                        className="w-3 h-3 rounded-full flex-shrink-0 shadow-sm"
                        style={{ backgroundColor: slice.color }}
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold text-white">
                            {h.symbol}
                          </span>
                          {h.isin && (
                            <span className="hidden sm:inline text-[10px] font-mono text-slate-400">
                              {h.isin}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-300 truncate max-w-[180px] sm:max-w-xs">
                          {h.name}
                        </p>
                      </div>
                    </div>

                    {/* Right: Actual % vs Target % & Drift Badge */}
                    <div className="flex items-center gap-3 sm:gap-4 flex-shrink-0 text-right">
                      <div className="text-right">
                        <div className="text-xs font-mono font-bold text-white">
                          {formatPct(h.actual_pct, false)}
                          <span className="text-[11px] font-normal text-slate-400 ml-1">
                            / Target {formatPct(h.target_pct, false)}
                          </span>
                        </div>
                        <div className="text-[11px] font-mono text-slate-300">
                          {formatEur(h.total_value_eur)}
                        </div>
                      </div>

                      <div className="w-32 flex justify-end">
                        {getDriftBadge(drift)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default AllocationDonut;
