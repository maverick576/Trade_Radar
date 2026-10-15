import React from "react";
import { Zap } from "lucide-react";

export interface StrategyBData {
  state: "LONG" | "SHORT" | "NEUTRAL";
  entry?: number | null;
  sl?: number | null;
  tp?: number | null;
  rr?: number;
  confirmed?: boolean;
  reason?: string;
}

interface StrategyBPanelProps {
  data?: StrategyBData;
}

export const StrategyBPanel: React.FC<StrategyBPanelProps> = ({ data }) => {
  if (!data) return null;

  const isLong = data.state === "LONG";
  const isShort = data.state === "SHORT";
  const isNeutral = data.state === "NEUTRAL";

  return (
    <div className="p-4 rounded-xl bg-surface border border-border shadow-sm space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-bold text-fg tracking-wide">
            Strategi B: Triple-EMA
          </h3>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`px-2 py-0.5 rounded text-xs font-bold font-mono border ${
              isLong
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                : isShort
                ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                : "bg-surface-2 border-border text-muted"
            }`}
          >
            {data.state}
          </span>
          {!isNeutral && data.confirmed && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              ✓ Konfirmasi
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      {isNeutral ? (
        <div className="p-3 rounded-lg bg-surface-2/40 text-xs text-muted leading-relaxed">
          {data.reason || "Belum ada sinyal crossover Triple-EMA (EMA 9 / 21 open / 50)."}
        </div>
      ) : (
        <div className="space-y-2">
          {/* Levels Table */}
          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
            <div className="p-2 rounded-lg bg-surface-2/50 border border-border">
              <div className="text-[10px] text-muted uppercase">Entry</div>
              <div className="font-bold text-fg mt-0.5">
                {data.entry?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20">
              <div className="text-[10px] text-rose-400 uppercase">Stop Loss</div>
              <div className="font-bold text-rose-400 mt-0.5">
                {data.sl?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <div className="text-[10px] text-emerald-400 uppercase">TP (1R)</div>
              <div className="font-bold text-emerald-400 mt-0.5">
                {data.tp?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          <p className="text-[11px] text-muted leading-relaxed mt-1">
            {data.reason}
          </p>
        </div>
      )}
    </div>
  );
};
