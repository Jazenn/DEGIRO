import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  PortfolioDailyHistoryRecord,
  Timeframe,
} from '../types/portfolio';
import { TimeframeSelector } from './TimeframeSelector';
import { formatEur, formatPct } from '../utils/metrics';

interface PortfolioChartProps {
  data: PortfolioDailyHistoryRecord[];
  timeframe: Timeframe;
  onTimeframeChange: (tf: Timeframe) => void;
}

export const PortfolioChart: React.FC<PortfolioChartProps> = ({
  data,
  timeframe,
  onTimeframeChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState<number>(800);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // ResizeObserver to track container width for pixel-perfect hover & aspect ratio
  useEffect(() => {
    if (!containerRef.current) return;
    const updateWidth = () => {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth;
        if (w > 0) setChartWidth(w);
      }
    };
    updateWidth();

    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect.width > 0) {
            setChartWidth(Math.round(entry.contentRect.width));
          }
        }
      });
      ro.observe(containerRef.current);
      return () => ro.disconnect();
    } else {
      window.addEventListener('resize', updateWidth);
      return () => window.removeEventListener('resize', updateWidth);
    }
  }, []);

  // Calculate return over the selected period
  const periodReturn = useMemo(() => {
    if (!data || data.length < 2) return { eur: 0, pct: 0 };
    const first = data[0];
    const last = data[data.length - 1];
    const eur = last.total_equity_eur - first.total_equity_eur;
    const pct =
      first.total_equity_eur > 0
        ? (eur / first.total_equity_eur) * 100
        : 0;
    return { eur, pct };
  }, [data]);

  // Chart coordinate calculations
  const {
    viewBoxWidth,
    viewBoxHeight,
    paddingLeft,
    paddingRight,
    paddingTop,
    paddingBottom,
    equityPath,
    equityAreaPath,
    investedPath,
    points,
    yGridLines,
    xLabels,
  } = useMemo(() => {
    const width = chartWidth || 800;
    const height = 340;
    const pLeft = 70;
    const pRight = 24;
    const pTop = 20;
    const pBottom = 40;
    const plotW = width - pLeft - pRight;
    const plotH = height - pTop - pBottom;

    if (!data || data.length === 0) {
      return {
        viewBoxWidth: width,
        viewBoxHeight: height,
        paddingLeft: pLeft,
        paddingRight: pRight,
        paddingTop: pTop,
        paddingBottom: pBottom,
        equityPath: '',
        equityAreaPath: '',
        investedPath: '',
        points: [],
        yGridLines: [],
        xLabels: [],
      };
    }

    let minVal = Infinity;
    let maxVal = -Infinity;

    data.forEach((d) => {
      if (d.total_equity_eur < minVal) minVal = d.total_equity_eur;
      if (d.total_equity_eur > maxVal) maxVal = d.total_equity_eur;
      if (d.invested_capital_eur < minVal) minVal = d.invested_capital_eur;
      if (d.invested_capital_eur > maxVal) maxVal = d.invested_capital_eur;
    });

    // Provide breathing room
    const padding = (maxVal - minVal) * 0.08 || 1000;
    const yMin = Math.max(0, Math.floor((minVal - padding) / 500) * 500);
    const yMax = Math.ceil((maxVal + padding) / 500) * 500;
    const yRange = yMax - yMin || 1;

    const n = data.length;
    const pts = data.map((d, i) => {
      const x = n > 1 ? pLeft + (i / (n - 1)) * plotW : pLeft + plotW / 2;
      const yEquity = pTop + plotH - ((d.total_equity_eur - yMin) / yRange) * plotH;
      const yInvested =
        pTop + plotH - ((d.invested_capital_eur - yMin) / yRange) * plotH;

      const dateObj = new Date(d.date);
      const nextDateObj = i < n - 1 ? new Date(data[i + 1].date) : undefined;

      let isHighlight = false;
      let label = '';

      switch (timeframe) {
        case '24H': {
          // Highlight every 4 hours and last point
          isHighlight = i % 4 === 0 || i === n - 1;
          label = dateObj.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
          break;
        }
        case '1W': {
          // Highlight each day
          isHighlight = true;
          label = dateObj.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric' });
          break;
        }
        case '1M': {
          // Fluctuations during the whole week, highlight for each last day of the week (Sunday/week boundary)
          const isSunday = dateObj.getDay() === 0;
          const isWeekEnd = nextDateObj ? nextDateObj.getDay() <= dateObj.getDay() : true;
          isHighlight = isSunday || isWeekEnd || i === n - 1;
          label = dateObj.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
          break;
        }
        case '3M': {
          // Fluctuations during the whole week, highlight for each last day of the week
          const isSunday = dateObj.getDay() === 0;
          const isWeekEnd = nextDateObj ? nextDateObj.getDay() <= dateObj.getDay() : true;
          isHighlight = isSunday || isWeekEnd || i === n - 1;
          label = dateObj.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
          break;
        }
        case '1Y': {
          // Highlight at the end of each month
          const isMonthEnd = nextDateObj ? nextDateObj.getMonth() !== dateObj.getMonth() : true;
          isHighlight = isMonthEnd || i === n - 1;
          label = dateObj.toLocaleDateString('en-GB', { month: 'short' });
          break;
        }
        case 'ALL':
        default: {
          const isQuarterEnd = nextDateObj
            ? Math.floor(nextDateObj.getMonth() / 3) !== Math.floor(dateObj.getMonth() / 3)
            : true;
          isHighlight = isQuarterEnd || i === 0 || i === n - 1;
          label = dateObj.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
          break;
        }
      }

      return { x, yEquity, yInvested, isHighlight, label, data: d };
    });

    // Generate line path
    const eqLine = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.yEquity.toFixed(1)}`)
      .join(' ');

    const bottomY = pTop + plotH;
    const eqArea =
      pts.length > 0
        ? `${eqLine} L ${pts[pts.length - 1].x.toFixed(1)} ${bottomY} L ${pts[0].x.toFixed(
            1
          )} ${bottomY} Z`
        : '';

    const invLine = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.yInvested.toFixed(1)}`)
      .join(' ');

    // 4 horizontal grid ticks
    const yGridCount = 4;
    const gridLines = [];
    for (let i = 0; i <= yGridCount; i++) {
      const val = yMin + (i / yGridCount) * yRange;
      const yPos = pTop + plotH - (i / yGridCount) * plotH;
      gridLines.push({
        y: yPos,
        value: val,
        formatted: `€${Math.round(val).toLocaleString()}`,
      });
    }

    // X date labels: take highlights with minimum spacing to prevent label crowding
    const highlightedPts = pts.filter((p) => p.isHighlight);
    const labels: Array<{ x: number; label: string }> = [];
    let lastX = -Infinity;
    const minDistance = plotW > 600 ? 50 : 40;

    for (let idx = 0; idx < highlightedPts.length; idx++) {
      const hp = highlightedPts[idx];
      const isLast = idx === highlightedPts.length - 1;

      if (isLast) {
        if (labels.length > 0 && hp.x - lastX < minDistance) {
          labels.pop(); // Remove previous to fit the last label cleanly
        }
        labels.push({ x: hp.x, label: hp.label });
      } else if (hp.x - lastX >= minDistance) {
        labels.push({ x: hp.x, label: hp.label });
        lastX = hp.x;
      }
    }

    // If no labels were produced (e.g. data length 1), add at least the single point
    if (labels.length === 0 && pts.length > 0) {
      labels.push({ x: pts[0].x, label: pts[0].label });
    }

    return {
      viewBoxWidth: width,
      viewBoxHeight: height,
      paddingLeft: pLeft,
      paddingRight: pRight,
      paddingTop: pTop,
      paddingBottom: pBottom,
      equityPath: eqLine,
      equityAreaPath: eqArea,
      investedPath: invLine,
      points: pts,
      yGridLines: gridLines,
      xLabels: labels,
    };
  }, [data, timeframe, chartWidth]);

  const activePoint = hoverIndex !== null && points[hoverIndex] ? points[hoverIndex] : null;

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!points || points.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const svgX = (clientX / rect.width) * viewBoxWidth;

    let closestIdx = 0;
    let closestDist = Infinity;
    points.forEach((p, idx) => {
      const dist = Math.abs(p.x - svgX);
      if (dist < closestDist) {
        closestDist = dist;
        closestIdx = idx;
      }
    });

    setHoverIndex(closestIdx);
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xl">
      {/* Chart Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold text-white tracking-tight">
              Portfolio Growth &amp; Valuation
            </h3>
            {data.length > 1 && (
              <span
                className={`text-xs font-mono font-semibold px-2 py-0.5 rounded-full ${
                  periodReturn.eur >= 0
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : 'bg-rose-500/15 text-rose-400'
                }`}
              >
                {formatPct(periodReturn.pct)} period
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Historical portfolio valuation compared against invested capital
          </p>
        </div>

        {/* Timeframe & Legend */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500 shadow-sm shadow-sky-500/50"></span>
              <span className="text-slate-300">Portfolio Value</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-dashed border-slate-400"></span>
              <span className="text-slate-400">Invested Capital</span>
            </div>
          </div>
          <TimeframeSelector selected={timeframe} onChange={onTimeframeChange} />
        </div>
      </div>

      {/* Interactive Hover HUD */}
      <div className="min-h-[38px] py-2 flex flex-wrap items-center justify-between text-xs font-mono border-b border-slate-800/40">
        {activePoint ? (
          <>
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Date:</span>
              <span className="font-semibold text-white">
                {(() => {
                  const d = new Date(activePoint.data.date);
                  const hasTime =
                    timeframe === '24H' ||
                    activePoint.data.date.includes('T') ||
                    activePoint.data.date.includes(':');
                  if (hasTime) {
                    return `${d.toLocaleDateString('en-GB', {
                      day: 'numeric',
                      month: 'short',
                    })}, ${d.toLocaleTimeString('en-GB', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}`;
                  }
                  return d.toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  });
                })()}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div>
                <span className="text-slate-400">Value: </span>
                <span className="font-bold text-sky-400">
                  {formatEur(activePoint.data.total_equity_eur)}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Invested: </span>
                <span className="font-medium text-slate-300">
                  {formatEur(activePoint.data.invested_capital_eur)}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Gain: </span>
                <span
                  className={`font-semibold ${
                    activePoint.data.unrealized_pnl_eur >= 0
                      ? 'text-emerald-400'
                      : 'text-rose-400'
                  }`}
                >
                  {formatEur(activePoint.data.unrealized_pnl_eur)} (
                  {formatPct(activePoint.data.unrealized_pnl_pct)})
                </span>
              </div>
            </div>
          </>
        ) : (
          <span className="text-slate-500 text-[11px]">
            Hover or touch the graph to inspect valuation at any date
          </span>
        )}
      </div>

      {/* SVG Canvas */}
      <div ref={containerRef} className="relative w-full h-64 sm:h-72 mt-3 select-none">
        <svg
          viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
          preserveAspectRatio="none"
          className="w-full h-full overflow-visible"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onTouchMove={(e) => {
            if (e.touches.length > 0) {
              const touch = e.touches[0];
              const rect = e.currentTarget.getBoundingClientRect();
              const clientX = touch.clientX - rect.left;
              const svgX = (clientX / rect.width) * viewBoxWidth;
              let closestIdx = 0;
              let closestDist = Infinity;
              points.forEach((p, idx) => {
                const dist = Math.abs(p.x - svgX);
                if (dist < closestDist) {
                  closestDist = dist;
                  closestIdx = idx;
                }
              });
              setHoverIndex(closestIdx);
            }
          }}
          onTouchEnd={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0284c7" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#0284c7" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Horizontal Grid lines */}
          {yGridLines.map((grid, idx) => (
            <g key={idx}>
              <line
                x1={paddingLeft}
                y1={grid.y}
                x2={viewBoxWidth - paddingRight}
                y2={grid.y}
                stroke="#334155"
                strokeOpacity="0.3"
                strokeWidth="1"
              />
              <text
                x={paddingLeft - 8}
                y={grid.y + 3}
                textAnchor="end"
                className="font-mono text-[10px] fill-slate-500"
              >
                {grid.formatted}
              </text>
            </g>
          ))}

          {/* X axis date ticks */}
          {xLabels.map((lbl, idx) => (
            <text
              key={idx}
              x={lbl.x}
              y={viewBoxHeight - 12}
              textAnchor="middle"
              className="font-mono text-[10px] fill-slate-500 font-medium select-none"
            >
              {lbl.label}
            </text>
          ))}

          {/* Area Fill for Portfolio Value */}
          {equityAreaPath && <path d={equityAreaPath} fill="url(#equityGrad)" />}

          {/* Invested Capital Line (dashed) */}
          {investedPath && (
            <path
              d={investedPath}
              fill="none"
              stroke="#64748b"
              strokeWidth="1.75"
              strokeDasharray="4 4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Portfolio Equity Line (solid) */}
          {equityPath && (
            <path
              d={equityPath}
              fill="none"
              stroke="#0284c7"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Highlight marker dots for key milestones */}
          {points.map((p, idx) => {
            if (!p.isHighlight) return null;
            const isHovered = activePoint?.data.date === p.data.date;
            return (
              <circle
                key={`hl-${idx}`}
                cx={p.x}
                cy={p.yEquity}
                r={isHovered ? 5 : 3}
                fill={isHovered ? '#38bdf8' : '#0284c7'}
                stroke="#0f172a"
                strokeWidth={isHovered ? 2 : 1.5}
                className="transition-all duration-150"
              />
            );
          })}

          {/* Active Hover Guide and Points */}
          {activePoint && (
            <g>
              <line
                x1={activePoint.x}
                y1={paddingTop}
                x2={activePoint.x}
                y2={viewBoxHeight - paddingBottom}
                stroke="#38bdf8"
                strokeWidth="1.25"
                strokeDasharray="3 3"
                strokeOpacity="0.75"
              />
              {/* Invested Dot */}
              <circle
                cx={activePoint.x}
                cy={activePoint.yInvested}
                r="3.5"
                fill="#64748b"
                stroke="#0f172a"
                strokeWidth="1.5"
              />
              {/* Equity Dot */}
              <circle
                cx={activePoint.x}
                cy={activePoint.yEquity}
                r="5"
                fill="#38bdf8"
                stroke="#0f172a"
                strokeWidth="2"
              />
            </g>
          )}
        </svg>
      </div>
    </div>
  );
};
