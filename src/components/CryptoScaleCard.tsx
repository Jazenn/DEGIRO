import React, { useState } from 'react';
import {
  Layers,
  TrendingDown,
  TrendingUp,
  SlidersHorizontal,
  Coins,
  ArrowDownRight,
  ArrowUpRight,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { PortfolioAssetSetting, CurrentAssetHoldingRecord } from '../types/portfolio';
import { calculateCryptoScaleMetrics } from '../utils/cryptoScale';

export interface CryptoScaleCardProps {
  cryptoSettings: PortfolioAssetSetting[];
  holdings: CurrentAssetHoldingRecord[];
  onOpenSettings?: () => void;
}

export const CryptoScaleCard: React.FC<CryptoScaleCardProps> = ({
  cryptoSettings,
  holdings,
  onOpenSettings,
}) => {
  // Filter for crypto assets only
  const cryptos = cryptoSettings.filter((s) => s.is_crypto);

  const [selectedSymbol, setSelectedSymbol] = useState<string>(() => {
    return cryptos.length > 0 ? cryptos[0].symbol : '';
  });

  // If selectedSymbol is no longer in cryptos, reset
  const activeSetting =
    cryptos.find((c) => c.symbol === selectedSymbol) || (cryptos.length > 0 ? cryptos[0] : null);

  if (!activeSetting) {
    return null;
  }

  // Find matching holding to get current live price
  const holding = holdings.find(
    (h) => h.symbol === activeSetting.symbol || h.name.toLowerCase() === activeSetting.display_name.toLowerCase()
  );

  // Default fallback prices if holding not found: BTC ~ 64320, ETH ~ 3210
  const fallbackPrice = activeSetting.symbol.includes('BTC')
    ? 64320
    : activeSetting.symbol.includes('ETH')
    ? 3210
    : 100;

  const currentPrice = holding && holding.current_price_eur > 0 ? holding.current_price_eur : fallbackPrice;

  const metrics = calculateCryptoScaleMetrics({
    currentPrice,
    buyDipTrigger: activeSetting.buy_dip_trigger,
    sellProfitTrigger: activeSetting.sell_profit_trigger,
    buyBudget: activeSetting.buy_budget,
  });

  const formatEur = (val: number | null) => {
    if (val === null || val === undefined) return '—';
    return new Intl.NumberFormat('en-IE', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: val >= 100 ? 0 : 2,
    }).format(val);
  };

  const formatPct = (val: number | null, withSign = true) => {
    if (val === null || val === undefined) return '—';
    const sign = withSign && val > 0 ? '+' : '';
    return `${sign}${val.toFixed(1)}%`;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 space-y-6 shadow-xl">
      {/* Header with Title, Multi-Asset Selector and Configure Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shadow-sm">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              Crypto Scale
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold tracking-wider">
                Discipline Bands
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Predefined dip accumulation buy zones &amp; staged take-profit targets
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Asset Pills for switching crypto */}
          {cryptos.length > 1 && (
            <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
              {cryptos.map((c) => {
                const isSelected = c.symbol === activeSetting.symbol;
                const shortLabel = c.symbol.replace('-EUR', '').replace('.DE', '');
                return (
                  <button
                    key={c.symbol}
                    onClick={() => setSelectedSymbol(c.symbol)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition ${
                      isSelected
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    {shortLabel}
                  </button>
                );
              })}
            </div>
          )}

          {onOpenSettings && (
            <button
              onClick={onOpenSettings}
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/80 text-xs font-medium font-mono transition flex items-center gap-1.5 shadow-sm"
              title="Configure Crypto Scale Triggers"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Configure Triggers</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Status & Current Price Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 items-center">
        <div>
          <span className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
            <Coins className="w-3.5 h-3.5 text-amber-400" />
            {activeSetting.display_name} ({activeSetting.symbol})
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
              {formatEur(currentPrice)}
            </span>
          </div>
        </div>

        <div>
          <span className="text-xs text-slate-400 font-mono block">Status Discipline</span>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold font-mono flex items-center gap-1.5 ${
                metrics.status === 'BUY_ZONE'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : metrics.status === 'PROFIT_ZONE'
                  ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                  : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
              }`}
            >
              {metrics.status === 'BUY_ZONE' && <Sparkles className="w-3.5 h-3.5" />}
              {metrics.status === 'PROFIT_ZONE' && <ShieldAlert className="w-3.5 h-3.5" />}
              {metrics.status === 'NEUTRAL' && <Layers className="w-3.5 h-3.5" />}
              {metrics.statusBadge.label}
            </span>
          </div>
        </div>

        <div className="text-xs font-mono text-slate-400 space-y-1">
          <div className="flex justify-between">
            <span>Target Weight:</span>
            <span className="text-slate-200 font-semibold">{activeSetting.target_pct.toFixed(1)}%</span>
          </div>
          {holding && (
            <div className="flex justify-between">
              <span>Actual Holdings:</span>
              <span className="text-slate-200 font-semibold">
                {holding.actual_pct.toFixed(1)}% ({formatEur(holding.total_value_eur)})
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Visual Position Scale Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-1 text-emerald-400 font-medium">
            <TrendingDown className="w-3 h-3" />
            Buy Zone: {formatEur(metrics.buyDipTrigger)}
          </span>
          <span className="text-slate-300 font-semibold">
            Current: {formatEur(currentPrice)}
          </span>
          <span className="flex items-center gap-1 text-rose-400 font-medium">
            <TrendingUp className="w-3 h-3" />
            Profit Target: {formatEur(metrics.sellProfitTrigger)}
          </span>
        </div>

        {/* Progress Bar Track */}
        <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden border border-slate-800 p-0.5 relative">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              metrics.status === 'BUY_ZONE'
                ? 'bg-emerald-500'
                : metrics.status === 'PROFIT_ZONE'
                ? 'bg-rose-500'
                : 'bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500'
            }`}
            style={{ width: `${Math.max(5, Math.min(100, metrics.progressPct))}%` }}
          />
        </div>
      </div>

      {/* 2-Column Action Cards: Dip Accumulation & Take-Profit Targets */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Next Buy Trigger Card */}
        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/90 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-mono font-semibold flex items-center gap-1.5">
              <ArrowDownRight className="w-3.5 h-3.5 text-emerald-400" />
              Accumulation Buy Zone
            </span>
            {metrics.distanceToBuyPct !== null && (
              <span
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                  metrics.distanceToBuyPct >= 0
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-slate-800 text-slate-300'
                }`}
              >
                {formatPct(metrics.distanceToBuyPct)}
              </span>
            )}
          </div>

          <div className="flex items-baseline justify-between mt-2">
            <div>
              <span className="text-2xl font-extrabold font-mono text-emerald-400">
                {formatEur(metrics.buyDipTrigger)}
              </span>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Execute automated buy when price drops to trigger
              </p>
            </div>
          </div>

          <div className="border-t border-slate-800/80 pt-2.5 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-400">Allocated Cash Budget:</span>
            <span className="text-emerald-400 font-bold bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded">
              Budget: {formatEur(metrics.buyBudget)}
            </span>
          </div>
        </div>

        {/* Staged Take-Profit Target Card */}
        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/90 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-mono font-semibold flex items-center gap-1.5">
              <ArrowUpRight className="w-3.5 h-3.5 text-rose-400" />
              Tier 1 Profit Target
            </span>
            {metrics.distanceToSellPct !== null && (
              <span
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                  metrics.distanceToSellPct <= 0
                    ? 'bg-rose-500/20 text-rose-300'
                    : 'bg-slate-800 text-slate-300'
                }`}
              >
                {formatPct(metrics.distanceToSellPct)}
              </span>
            )}
          </div>

          <div className="flex items-baseline justify-between mt-2">
            <div>
              <span className="text-2xl font-extrabold font-mono text-rose-400">
                {formatEur(metrics.sellProfitTrigger)}
              </span>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Scale out and rebalance profits into core ETFs
              </p>
            </div>
          </div>

          <div className="border-t border-slate-800/80 pt-2.5 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-400">Discipline Rule:</span>
            <span className="text-rose-400 font-bold bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded">
              Take 15% Profit
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
