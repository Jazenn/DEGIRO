import React, { useState } from 'react';
import {
  RotateCw,
  Database,
  ShieldCheck,
  Activity,
} from 'lucide-react';
import { DashboardData, Timeframe } from '../types/portfolio';
import { MetricCards } from './MetricCards';
import { PortfolioChart } from './PortfolioChart';
import { AllocationDonut } from './AllocationDonut';
import { RebalanceCockpit } from './RebalanceCockpit';
import { filterPortfolioHistory } from '../utils/timeframe';

interface DashboardProps {
  initialData: DashboardData;
  onRefresh?: () => Promise<void>;
  isRefreshing?: boolean;
}

export const Dashboard: React.FC<DashboardProps> = ({
  initialData,
  onRefresh,
  isRefreshing = false,
}) => {
  const [data, setData] = useState<DashboardData>(initialData);
  const [timeframe, setTimeframe] = useState<Timeframe>('ALL');

  // Keep internal state synced if initialData changes
  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  const filteredHistory = filterPortfolioHistory(data.history, timeframe);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-6 sm:py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-6 sm:space-y-8">
      {/* Top Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center font-bold font-mono text-sm shadow-sm">
              DG
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              DEGIRO Portfolio
            </h1>
            {data.isDemo ? (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
                <Database className="w-3 h-3" />
                Demo Mode
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                Neon Connected
              </span>
            )}
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Executive FinTech dashboard &bull; Sub-50ms pre-aggregated snapshots
          </p>
        </div>

        <div className="flex items-center gap-3">
          {data.lastUpdated && (
            <div className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl">
              <Activity className="w-3.5 h-3.5 text-slate-500" />
              <span>
                Updated {new Date(data.lastUpdated).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          )}

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 hover:border-slate-700 text-xs font-medium font-mono transition flex items-center gap-2 shadow-sm disabled:opacity-50"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
              <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
            </button>
          )}
        </div>
      </header>

      {/* Prominent Metric Cards */}
      <section aria-label="Key Portfolio Metrics">
        <MetricCards metrics={data.metrics} />
      </section>

      {/* Interactive Performance Curve */}
      <section aria-label="Portfolio Growth Chart">
        <PortfolioChart
          data={filteredHistory}
          timeframe={timeframe}
          onTimeframeChange={setTimeframe}
        />
      </section>

      {/* Asset Allocation Donut Chart */}
      <section aria-label="Asset Allocation & Drift Analysis">
        <AllocationDonut
          holdings={data.holdings}
          totalPortfolioValue={data.metrics.totalPortfolioValue}
        />
      </section>

      {/* Interactive Monthly Rebalancing Cockpit */}
      <section aria-label="Interactive Monthly Rebalancing Cockpit">
        <RebalanceCockpit
          holdings={data.holdings}
          totalPortfolioValue={data.metrics.totalPortfolioValue}
        />
      </section>
    </div>
  );
};

export default Dashboard;
