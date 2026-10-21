import React, { useState, useMemo } from 'react';
import {
  RotateCw,
  Database,
  ShieldCheck,
  Activity,
  Settings,
  Menu,
  Upload,
  CheckCircle2,
  AlertCircle,
  X,
} from 'lucide-react';
import { DashboardData, Timeframe, PortfolioAssetSetting } from '../types/portfolio';
import { MetricCards } from './MetricCards';
import { PortfolioChart } from './PortfolioChart';
import { AllocationDonut } from './AllocationDonut';
import { RebalanceCockpit } from './RebalanceCockpit';
import { CryptoScaleCard } from './CryptoScaleCard';
import { SettingsModal } from './SettingsModal';
import { MobileDrawer } from './MobileDrawer';
import { CsvUploadModal } from './CsvUploadModal';
import { filterPortfolioHistory, getAssetPortfolioHistory } from '../utils/timeframe';
import {
  saveAssetSettings,
  applySettingsToDashboardData,
  getDefaultAssetSettings,
} from '../services/portfolioData';
import { triggerPriceRefresh } from '../services/priceRefresh';
import { CsvParseResult } from '../utils/csvParser';

interface DashboardProps {
  initialData: DashboardData;
  onRefresh?: () => Promise<void>;
  isRefreshing?: boolean;
}

interface ToastNotification {
  type: 'success' | 'error' | 'info';
  message: string;
}

export const Dashboard: React.FC<DashboardProps> = ({
  initialData,
  onRefresh,
  isRefreshing: externalRefreshing = false,
}) => {
  const [data, setData] = useState<DashboardData>(() => ({
    ...initialData,
    assetSettings: initialData.assetSettings || getDefaultAssetSettings(),
  }));
  const [timeframe, setTimeframe] = useState<Timeframe>('ALL');
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [internalRefreshing, setInternalRefreshing] = useState(false);
  const [toast, setToast] = useState<ToastNotification | null>(null);

  const isRefreshing = externalRefreshing || internalRefreshing;

  // Keep internal state synced if initialData changes
  React.useEffect(() => {
    setData({
      ...initialData,
      assetSettings: initialData.assetSettings || getDefaultAssetSettings(),
    });
  }, [initialData]);

  // Auto-dismiss toast notification after 4.5 seconds
  React.useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      setToast(null);
    }, 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  const assetFilteredHistory = useMemo(
    () => getAssetPortfolioHistory(data.history, selectedAsset),
    [data.history, selectedAsset]
  );
  const filteredHistory = filterPortfolioHistory(assetFilteredHistory, timeframe);

  const handleSaveSettings = async (updatedSettings: PortfolioAssetSetting[]) => {
    // Persist settings (to Neon Serverless DB or localStorage)
    await saveAssetSettings(updatedSettings);

    // Apply updated settings in-memory to immediately refresh rebalancing & crypto views
    const nextData = applySettingsToDashboardData(data, updatedSettings);
    setData(nextData);
    setToast({
      type: 'success',
      message: 'Portfolio strategy settings saved successfully',
    });
    if (onRefresh) {
      await onRefresh();
    }
  };

  const handlePriceRefresh = async () => {
    if (isRefreshing) return;
    setInternalRefreshing(true);
    try {
      const refreshResult = await triggerPriceRefresh({ isDemo: data.isDemo });
      if (onRefresh) {
        await onRefresh();
      }
      if (refreshResult.success) {
        setData((prev) => ({
          ...prev,
          lastUpdated: refreshResult.timestamp,
        }));
        setToast({
          type: 'success',
          message: refreshResult.message || 'Prices refreshed successfully',
        });
      } else {
        setToast({
          type: 'error',
          message: refreshResult.message || 'Failed to refresh prices',
        });
      }
    } catch (err: any) {
      setToast({
        type: 'error',
        message: err?.message || 'Error occurred during price refresh',
      });
    } finally {
      setInternalRefreshing(false);
    }
  };

  const handleUploadSuccess = async (result: CsvParseResult) => {
    setToast({
      type: 'success',
      message: `Processed ${result.rowsProcessed} rows: ${result.newRows} new transaction(s) stored, ${result.duplicatesSkipped} duplicate(s) skipped`,
    });
    if (onRefresh) {
      await onRefresh();
    }
  };

  const hasCrypto = Boolean(
    data.assetSettings && data.assetSettings.some((s) => s.is_crypto)
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-6 sm:py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-6 sm:space-y-8">
      {/* Top Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center justify-between">
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

          {/* Mobile Menu Hamburger Button */}
          <button
            onClick={() => setIsMobileDrawerOpen(true)}
            aria-label="Open navigation menu"
            className="md:hidden min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800 transition"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>

        {/* Desktop Header Actions */}
        <div className="hidden md:flex items-center gap-3">
          {data.lastUpdated && (
            <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl">
              <Activity className="w-3.5 h-3.5 text-slate-500" />
              <span>
                Updated{' '}
                {new Date(data.lastUpdated).toLocaleTimeString('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          )}

          {/* Upload CSV Button */}
          <button
            onClick={() => setIsUploadOpen(true)}
            aria-label="Upload CSV"
            title="Upload DEGIRO Transactions / Account CSV"
            className="min-h-[44px] px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 hover:border-slate-700 text-xs font-medium font-mono transition flex items-center gap-2 shadow-sm"
          >
            <Upload className="w-4 h-4 text-emerald-400" />
            <span>Upload CSV</span>
          </button>

          {/* Settings Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            aria-label="Strategy and Crypto Settings"
            title="Configure Strategy & Crypto Scale Settings"
            className="min-h-[44px] px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 hover:border-slate-700 text-xs font-medium font-mono transition flex items-center gap-2 shadow-sm"
          >
            <Settings className="w-4 h-4 text-slate-400" />
            <span>Settings</span>
          </button>

          {/* Refresh Prices Button */}
          <button
            onClick={handlePriceRefresh}
            disabled={isRefreshing}
            aria-label="Refresh Prices"
            title="Trigger on-demand price fetcher"
            className="min-h-[44px] px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 hover:border-slate-700 text-xs font-medium font-mono transition flex items-center gap-2 shadow-sm disabled:opacity-50"
          >
            <RotateCw
              className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`}
            />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </header>

      {/* Prominent Metric Cards */}
      <section id="section-metrics" aria-label="Key Portfolio Metrics">
        <MetricCards metrics={data.metrics} />
      </section>

      {/* Interactive Portfolio History Growth */}
      <section id="section-chart" aria-label="Portfolio Growth Chart">
        <PortfolioChart
          data={filteredHistory}
          timeframe={timeframe}
          onTimeframeChange={setTimeframe}
          holdings={data.holdings}
          selectedAsset={selectedAsset}
          onSelectedAssetChange={setSelectedAsset}
        />
      </section>

      {/* Asset Allocation Donut Chart */}
      <section id="section-allocation" aria-label="Asset Allocation & Drift Analysis">
        <AllocationDonut
          holdings={data.holdings}
          totalPortfolioValue={data.metrics.totalPortfolioValue}
        />
      </section>

      {/* Interactive Monthly Rebalancing Cockpit */}
      <section id="section-rebalance" aria-label="Interactive Monthly Rebalancing Cockpit">
        <RebalanceCockpit
          holdings={data.holdings}
          totalPortfolioValue={data.metrics.totalPortfolioValue}
          assetSettings={data.assetSettings}
        />
      </section>

      {/* Crypto Scale Visualizer Card */}
      {hasCrypto && (
        <section id="section-crypto" aria-label="Crypto Scale">
          <CryptoScaleCard
            cryptoSettings={data.assetSettings!}
            holdings={data.holdings}
            onOpenSettings={() => setIsSettingsOpen(true)}
          />
        </section>
      )}

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={data.assetSettings || []}
        onSave={handleSaveSettings}
      />

      {/* Mobile Drawer Menu */}
      <MobileDrawer
        isOpen={isMobileDrawerOpen}
        onClose={() => setIsMobileDrawerOpen(false)}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onRefreshPrices={handlePriceRefresh}
        isRefreshing={isRefreshing}
        hasCrypto={hasCrypto}
      />

      {/* CSV Upload Modal */}
      <CsvUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />

      {/* Floating Toast Notification */}
      {toast && (
        <div
          role="status"
          className={`fixed bottom-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-2xl border shadow-2xl text-xs sm:text-sm font-medium animate-in fade-in slide-in-from-bottom-3 max-w-sm sm:max-w-md ${
            toast.type === 'success'
              ? 'bg-emerald-950/90 border-emerald-500/30 text-emerald-200'
              : 'bg-rose-950/90 border-rose-500/30 text-rose-200'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          )}
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => setToast(null)}
            aria-label="Dismiss notification"
            className="min-h-[44px] min-w-[44px] flex items-center justify-center text-slate-400 hover:text-white -mr-2"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
