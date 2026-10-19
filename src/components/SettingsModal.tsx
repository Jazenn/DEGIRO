import React, { useState, useEffect } from 'react';
import {
  X,
  Sliders,
  CheckCircle2,
  AlertCircle,
  PieChart,
  Layers,
  Save,
  RotateCcw,
} from 'lucide-react';
import { PortfolioAssetSetting } from '../types/portfolio';
import {
  validateRebalancingTargets,
  validateCryptoTriggerSettings,
} from '../utils/settingsValidation';

export interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: PortfolioAssetSetting[];
  onSave: (updatedSettings: PortfolioAssetSetting[]) => Promise<void> | void;
}

type SettingsTab = 'targets' | 'crypto';

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>('targets');
  const [localSettings, setLocalSettings] = useState<PortfolioAssetSetting[]>(settings);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Sync internal state when opened or settings prop changes
  useEffect(() => {
    if (isOpen) {
      setLocalSettings(settings);
      setErrorMessage(null);
    }
  }, [isOpen, settings]);

  if (!isOpen) {
    return null;
  }

  // Calculate real-time sum
  const weightsMap: Record<string, number> = {};
  for (const s of localSettings) {
    weightsMap[s.symbol] = s.target_pct;
  }
  const targetValidation = validateRebalancingTargets(weightsMap);
  const isHundred = targetValidation.valid;
  const currentTotal = targetValidation.sum;

  const handleTargetChange = (symbol: string, valueStr: string) => {
    setErrorMessage(null);
    const num = parseFloat(valueStr);
    setLocalSettings((prev) =>
      prev.map((s) =>
        s.symbol === symbol
          ? { ...s, target_pct: Number.isNaN(num) ? 0 : num }
          : s
      )
    );
  };

  const handleCryptoChange = (
    symbol: string,
    field: 'buy_dip_trigger' | 'sell_profit_trigger' | 'buy_budget' | 'sell_profit_pct',
    valueStr: string
  ) => {
    setErrorMessage(null);
    const num = valueStr.trim() === '' ? null : parseFloat(valueStr);
    setLocalSettings((prev) =>
      prev.map((s) =>
        s.symbol === symbol
          ? {
              ...s,
              [field]: num !== null && !Number.isNaN(num) ? num : null,
            }
          : s
      )
    );
  };

  const handleReset = () => {
    setLocalSettings(settings);
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // 1. Validate rebalancing targets
    const targetCheck = validateRebalancingTargets(weightsMap);
    if (!targetCheck.valid) {
      setErrorMessage(targetCheck.error || 'Target percentages must equal 100%.');
      setActiveTab('targets');
      return;
    }

    // 2. Validate crypto triggers
    for (const s of localSettings) {
      if (s.is_crypto) {
        const cryptoCheck = validateCryptoTriggerSettings({
          buy_dip_trigger: s.buy_dip_trigger,
          sell_profit_trigger: s.sell_profit_trigger,
          sell_profit_pct: s.sell_profit_pct,
          buy_budget: s.buy_budget,
        });
        if (!cryptoCheck.valid) {
          const firstErr = Object.values(cryptoCheck.errors)[0];
          setErrorMessage(`${s.display_name}: ${firstErr}`);
          setActiveTab('crypto');
          return;
        }
      }
    }

    try {
      setIsSaving(true);
      await onSave(localSettings);
      onClose();
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to persist settings. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const cryptoAssets = localSettings.filter((s) => s.is_crypto);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2
                id="settings-modal-title"
                className="text-lg font-bold text-white tracking-tight"
              >
                Portfolio Strategy &amp; Crypto Scale Settings
              </h2>
              <p className="text-xs text-slate-400">
                Adjust allocation targets &amp; cryptocurrency execution triggers
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="h-8 w-8 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition border border-slate-700/60"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-800 bg-slate-950/40 px-5 pt-3 gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('targets')}
            className={`px-4 py-2 text-xs font-mono font-medium rounded-t-xl transition flex items-center gap-2 border-t border-x ${
              activeTab === 'targets'
                ? 'bg-slate-900 text-white border-slate-800 border-b-transparent shadow-sm'
                : 'text-slate-400 hover:text-slate-200 border-transparent'
            }`}
          >
            <PieChart className="w-3.5 h-3.5 text-sky-400" />
            <span>Target Allocations</span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                isHundred
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-amber-500/20 text-amber-300'
              }`}
            >
              {currentTotal.toFixed(1)}%
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('crypto')}
            className={`px-4 py-2 text-xs font-mono font-medium rounded-t-xl transition flex items-center gap-2 border-t border-x ${
              activeTab === 'crypto'
                ? 'bg-slate-900 text-white border-slate-800 border-b-transparent shadow-sm'
                : 'text-slate-400 hover:text-slate-200 border-transparent'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-amber-400" />
            <span>Crypto Triggers ({cryptoAssets.length})</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Target Allocations Tab */}
          {activeTab === 'targets' && (
            <div className="space-y-4">
              {/* Real-time total indicator header */}
              <div
                className={`p-3.5 rounded-xl border flex items-center justify-between text-xs font-mono ${
                  isHundred
                    ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-200'
                    : 'bg-amber-950/30 border-amber-800/60 text-amber-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  {isHundred ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                  )}
                  <span>
                    {isHundred
                      ? 'Target allocations are balanced.'
                      : `Target sum must equal 100% (${(100 - currentTotal).toFixed(1)}% remaining).`}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 font-bold">
                  <span>Total:</span>
                  <span
                    className={`text-sm px-2 py-0.5 rounded font-extrabold ${
                      isHundred
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-amber-500/20 text-amber-400'
                    }`}
                  >
                    {currentTotal.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Asset list input fields */}
              <div className="space-y-2.5">
                {localSettings.map((asset) => (
                  <div
                    key={asset.symbol}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-white text-xs sm:text-sm truncate">
                          {asset.display_name}
                        </span>
                        {asset.is_crypto && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
                            Crypto
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        {asset.symbol}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <label
                        htmlFor={`input-target-${asset.symbol}`}
                        className="text-xs text-slate-400 font-mono"
                      >
                        {asset.display_name} ({asset.symbol}) Target:
                      </label>
                      <div className="relative">
                        <input
                          id={`input-target-${asset.symbol}`}
                          aria-label={`${asset.display_name} (${asset.symbol}) Target`}
                          type="number"
                          step="0.1"
                          min="0"
                          max="100"
                          value={asset.target_pct}
                          onChange={(e) => handleTargetChange(asset.symbol, e.target.value)}
                          className="w-24 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-right font-mono font-bold text-white text-sm focus:outline-none focus:border-sky-500 transition pr-7"
                        />
                        <span className="absolute right-2.5 top-1.5 text-xs text-slate-400 font-mono pointer-events-none">
                          %
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Crypto Triggers Tab */}
          {activeTab === 'crypto' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                Configure buy zones, staged exit targets, and cash deployment budgets for your cryptocurrency positions.
              </p>

              {cryptoAssets.map((crypto) => (
                <div
                  key={crypto.symbol}
                  className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-4"
                >
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <span className="font-bold text-white text-sm flex items-center gap-2">
                      <Layers className="w-4 h-4 text-amber-400" />
                      {crypto.display_name} ({crypto.symbol})
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      Rebalancing Target: {crypto.target_pct.toFixed(1)}%
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {/* Dip Buy Trigger */}
                    <div className="space-y-1">
                      <label
                        htmlFor={`buy-trigger-${crypto.symbol}`}
                        className="block text-[11px] font-mono text-emerald-400 font-semibold"
                      >
                        Buy Dip Trigger (€)
                      </label>
                      <input
                        id={`buy-trigger-${crypto.symbol}`}
                        aria-label={`Buy Dip Trigger (${crypto.symbol})`}
                        type="number"
                        step="10"
                        min="0"
                        value={crypto.buy_dip_trigger ?? ''}
                        placeholder="e.g. 58500"
                        onChange={(e) =>
                          handleCryptoChange(crypto.symbol, 'buy_dip_trigger', e.target.value)
                        }
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 font-mono font-bold text-emerald-400 text-sm focus:outline-none focus:border-emerald-500 transition"
                      />
                      <span className="text-[10px] text-slate-500 block">
                        Accumulation trigger
                      </span>
                    </div>

                    {/* Profit Target */}
                    <div className="space-y-1">
                      <label
                        htmlFor={`sell-trigger-${crypto.symbol}`}
                        className="block text-[11px] font-mono text-rose-400 font-semibold"
                      >
                        Profit Target (€)
                      </label>
                      <input
                        id={`sell-trigger-${crypto.symbol}`}
                        aria-label={`Profit Target (${crypto.symbol})`}
                        type="number"
                        step="10"
                        min="0"
                        value={crypto.sell_profit_trigger ?? ''}
                        placeholder="e.g. 75420"
                        onChange={(e) =>
                          handleCryptoChange(crypto.symbol, 'sell_profit_trigger', e.target.value)
                        }
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 font-mono font-bold text-rose-400 text-sm focus:outline-none focus:border-rose-500 transition"
                      />
                      <span className="text-[10px] text-slate-500 block">
                        Stage 1 exit target
                      </span>
                    </div>

                    {/* Profit-Taking Sell % */}
                    <div className="space-y-1">
                      <label
                        htmlFor={`sell-profit-pct-${crypto.symbol}`}
                        className="block text-[11px] font-mono text-purple-400 font-semibold"
                      >
                        Profit Sell (%)
                      </label>
                      <input
                        id={`sell-profit-pct-${crypto.symbol}`}
                        aria-label={`Profit Sell Percentage (${crypto.symbol})`}
                        type="number"
                        step="1"
                        min="1"
                        max="100"
                        value={crypto.sell_profit_pct ?? ''}
                        placeholder="15"
                        onChange={(e) =>
                          handleCryptoChange(crypto.symbol, 'sell_profit_pct', e.target.value)
                        }
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 font-mono font-bold text-purple-400 text-sm focus:outline-none focus:border-purple-500 transition"
                      />
                      <span className="text-[10px] text-slate-500 block">
                        Staged exit % (default 15%)
                      </span>
                    </div>

                    {/* Buy Budget */}
                    <div className="space-y-1">
                      <label
                        htmlFor={`budget-${crypto.symbol}`}
                        className="block text-[11px] font-mono text-sky-400 font-semibold"
                      >
                        Cash Budget (€)
                      </label>
                      <input
                        id={`budget-${crypto.symbol}`}
                        aria-label={`Cash Budget (${crypto.symbol})`}
                        type="number"
                        step="10"
                        min="0"
                        value={crypto.buy_budget ?? ''}
                        placeholder="e.g. 350"
                        onChange={(e) =>
                          handleCryptoChange(crypto.symbol, 'buy_budget', e.target.value)
                        }
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 font-mono font-bold text-sky-400 text-sm focus:outline-none focus:border-sky-500 transition"
                      />
                      <span className="text-[10px] text-slate-500 block">
                        Allocated deposit
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Validation Error Banner */}
          {errorMessage && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Modal Footer Controls */}
          <div className="flex items-center justify-between pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-1.5 rounded-xl text-slate-400 hover:text-slate-200 text-xs font-mono transition flex items-center gap-1.5 hover:bg-slate-800"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-mono font-medium transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-mono font-semibold transition flex items-center gap-2 shadow-lg shadow-sky-600/20 disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{isSaving ? 'Saving...' : 'Save Settings'}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
