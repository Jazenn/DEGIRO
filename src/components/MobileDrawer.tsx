import React, { useEffect } from 'react';
import {
  X,
  RotateCw,
  Upload,
  Settings,
  TrendingUp,
  PieChart,
  SlidersHorizontal,
  Coins,
  Gauge,
} from 'lucide-react';

export interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenUpload: () => void;
  onOpenSettings: () => void;
  onRefreshPrices: () => void;
  isRefreshing?: boolean;
  hasCrypto?: boolean;
}

export const MobileDrawer: React.FC<MobileDrawerProps> = ({
  isOpen,
  onClose,
  onOpenUpload,
  onOpenSettings,
  onRefreshPrices,
  isRefreshing = false,
  hasCrypto = false,
}) => {
  // Prevent background scrolling when drawer is open on mobile
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const scrollToSection = (id: string) => {
    onClose();
    setTimeout(() => {
      const element = document.getElementById(id);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 150);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mobile-drawer-title"
      className="fixed inset-0 z-50 flex flex-col justify-end sm:justify-center sm:items-center bg-slate-950/80 backdrop-blur-sm"
    >
      {/* Backdrop tap area */}
      <div
        className="absolute inset-0"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Container (Bottom Sheet on mobile, centered card on tablet/desktop) */}
      <div className="relative w-full sm:max-w-md bg-slate-900 border-t sm:border border-slate-800 rounded-t-3xl sm:rounded-2xl shadow-2xl overflow-hidden z-10 max-h-[90vh] flex flex-col animate-in slide-in-from-bottom duration-200">
        {/* Handle bar for bottom sheet visual cue */}
        <div className="sm:hidden flex justify-center pt-3 pb-1">
          <div className="w-12 h-1.5 bg-slate-700 rounded-full" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div>
            <h2 id="mobile-drawer-title" className="text-base font-bold text-white">
              Navigation &amp; Actions
            </h2>
            <p className="text-xs text-slate-400">Quick portfolio management</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close navigation menu"
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Navigation & Actions List */}
        <div className="p-4 space-y-4 overflow-y-auto">
          {/* Quick Actions */}
          <div className="space-y-2">
            <span className="text-xs font-mono font-medium text-slate-400 uppercase tracking-wider px-2 block">
              Actions
            </span>

            {/* Refresh Prices */}
            <button
              onClick={() => {
                onRefreshPrices();
              }}
              disabled={isRefreshing}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-600 transition flex items-center justify-between disabled:opacity-50"
            >
              <div className="flex items-center gap-3">
                <RotateCw
                  className={`w-4 h-4 text-sky-400 ${isRefreshing ? 'animate-spin' : ''}`}
                />
                <span className="text-sm font-medium">
                  {isRefreshing ? 'Refreshing Prices...' : 'Refresh Prices'}
                </span>
              </div>
              <span className="text-xs font-mono text-slate-400">On-demand</span>
            </button>

            {/* Upload CSV */}
            <button
              onClick={() => {
                onClose();
                onOpenUpload();
              }}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-600 transition flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <Upload className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium">Upload CSV</span>
              </div>
              <span className="text-xs font-mono text-slate-400">Files / Downloads</span>
            </button>

            {/* Portfolio Settings */}
            <button
              onClick={() => {
                onClose();
                onOpenSettings();
              }}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-600 transition flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <Settings className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-medium">Portfolio Settings</span>
              </div>
              <span className="text-xs font-mono text-slate-400">Targets &amp; Crypto</span>
            </button>
          </div>

          {/* Jump to Sections */}
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <span className="text-xs font-mono font-medium text-slate-400 uppercase tracking-wider px-2 block">
              Sections
            </span>

            <button
              onClick={() => scrollToSection('section-metrics')}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl hover:bg-slate-800/60 text-slate-300 hover:text-white transition flex items-center gap-3 text-left"
            >
              <Gauge className="w-4 h-4 text-sky-400" />
              <span className="text-sm font-medium">Metrics Overview</span>
            </button>

            <button
              onClick={() => scrollToSection('section-chart')}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl hover:bg-slate-800/60 text-slate-300 hover:text-white transition flex items-center gap-3 text-left"
            >
              <TrendingUp className="w-4 h-4 text-indigo-400" />
              <span className="text-sm font-medium">Growth Chart</span>
            </button>

            <button
              onClick={() => scrollToSection('section-allocation')}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl hover:bg-slate-800/60 text-slate-300 hover:text-white transition flex items-center gap-3 text-left"
            >
              <PieChart className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-medium">Asset Allocation</span>
            </button>

            <button
              onClick={() => scrollToSection('section-rebalance')}
              className="w-full min-h-[44px] px-4 py-3 rounded-xl hover:bg-slate-800/60 text-slate-300 hover:text-white transition flex items-center gap-3 text-left"
            >
              <SlidersHorizontal className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium">Rebalance Cockpit</span>
            </button>

            {hasCrypto && (
              <button
                onClick={() => scrollToSection('section-crypto')}
                className="w-full min-h-[44px] px-4 py-3 rounded-xl hover:bg-slate-800/60 text-slate-300 hover:text-white transition flex items-center gap-3 text-left"
              >
                <Coins className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium">Crypto Scale</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
