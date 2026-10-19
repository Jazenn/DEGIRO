import React from 'react';
import { Timeframe } from '../types/portfolio';

interface TimeframeSelectorProps {
  selected: Timeframe;
  onChange: (timeframe: Timeframe) => void;
}

const TIMEFRAMES: Timeframe[] = ['1M', '3M', '1Y', 'ALL'];

export const TimeframeSelector: React.FC<TimeframeSelectorProps> = ({
  selected,
  onChange,
}) => {
  return (
    <div className="inline-flex items-center p-1 rounded-xl bg-slate-950 border border-slate-800 shadow-inner">
      {TIMEFRAMES.map((tf) => {
        const isActive = selected === tf;
        return (
          <button
            key={tf}
            type="button"
            data-active={isActive ? 'true' : 'false'}
            onClick={() => onChange(tf)}
            className={`px-3 py-1.5 text-xs font-mono font-medium rounded-lg transition-all ${
              isActive
                ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30 shadow-sm font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
            }`}
          >
            {tf}
          </button>
        );
      })}
    </div>
  );
};
