import React from "react";
import { BarChart3, TrendingUp, TrendingDown } from "lucide-react";
import type { TradeRecordItem, JournalKPIs } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface JournalRDistributionProps {
  trades: TradeRecordItem[];
  kpis: JournalKPIs | null;
  isLoading?: boolean;
}

interface BinItem {
  label: string;
  min: number;
  max: number;
  count: number;
  isPositive: boolean;
}

export const JournalRDistribution: React.FC<JournalRDistributionProps> = ({
  trades,
  kpis,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-64 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat distribusi R...
      </div>
    );
  }

  // Define 8 standard bins:
  // [-inf, -2), [-2, -1.5), [-1.5, -1), [-1, 0), [0, 1), [1, 1.5), [1.5, 2), [2, inf)
  const bins: BinItem[] = [
    { label: "< -2.0R", min: -Infinity, max: -2.0, count: 0, isPositive: false },
    { label: "-2.0 to -1.5R", min: -2.0, max: -1.5, count: 0, isPositive: false },
    { label: "-1.5 to -1.0R", min: -1.5, max: -1.0, count: 0, isPositive: false },
    { label: "-1.0 to 0.0R", min: -1.0, max: 0.0, count: 0, isPositive: false },
    { label: "0.0 to +1.0R", min: 0.0, max: 1.0, count: 0, isPositive: true },
    { label: "+1.0 to +1.5R", min: 1.0, max: 1.5, count: 0, isPositive: true },
    { label: "+1.5 to +2.0R", min: 1.5, max: 2.0, count: 0, isPositive: true },
    { label: "> +2.0R", min: 2.0, max: Infinity, count: 0, isPositive: true },
  ];

  trades.forEach((t) => {
    const r = t.pnl_r;
    for (const bin of bins) {
      if (r >= bin.min && r < bin.max) {
        bin.count++;
        break;
      }
    }
  });

  const maxCount = Math.max(1, ...bins.map((b) => b.count));

  // Compute largest win and loss
  let maxWinR = 0;
  let maxLossR = 0;
  trades.forEach((t) => {
    if (t.pnl_r > maxWinR) maxWinR = t.pnl_r;
    if (t.pnl_r < maxLossR) maxLossR = t.pnl_r;
  });

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-accent/10 text-accent">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Distribusi Hasil (R-Multiple)</h3>
            <p className="text-xs text-muted">
              Frekuensi hasil trade berdasarkan rasio resiko/hasil (R)
            </p>
          </div>
        </div>

        {kpis && (
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-emerald-400">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Avg Win: +{formatIdNumber(kpis.avg_win_r, 2)}R</span>
            </div>
            <div className="flex items-center gap-1.5 text-rose-400">
              <TrendingDown className="w-3.5 h-3.5" />
              <span>Avg Loss: {formatIdNumber(kpis.avg_loss_r, 2)}R</span>
            </div>
          </div>
        )}
      </div>

      {/* Histogram bars */}
      {trades.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-muted text-xs">
          Belum ada data distribusi trade tertutup.
        </div>
      ) : (
        <div className="flex flex-col gap-2 pt-2">
          <div className="grid grid-cols-8 gap-2 items-end h-36 border-b border-border/60 pb-1">
            {bins.map((bin, idx) => {
              const heightPct = Math.round((bin.count / maxCount) * 100);
              return (
                <div key={idx} className="flex flex-col items-center h-full justify-end group">
                  <span className="text-[10px] font-mono text-muted mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {bin.count}
                  </span>
                  <div
                    className={`w-full rounded-t-md transition-all duration-300 ${
                      bin.isPositive
                        ? "bg-emerald-500/80 hover:bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                        : "bg-rose-500/80 hover:bg-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)]"
                    }`}
                    style={{ height: `${Math.max(4, heightPct)}%` }}
                  />
                </div>
              );
            })}
          </div>

          {/* Bin labels */}
          <div className="grid grid-cols-8 gap-2 text-center">
            {bins.map((bin, idx) => (
              <div key={idx} className="text-[9px] text-muted font-mono truncate" title={bin.label}>
                {bin.label}
              </div>
            ))}
          </div>

          {/* Quick stats footer */}
          <div className="flex items-center justify-between text-xs text-muted pt-2 border-t border-border/40 mt-1">
            <span>
              Win Terbesar:{" "}
              <strong className="text-emerald-400 font-mono">
                +{formatIdNumber(maxWinR, 2)} R
              </strong>
            </span>
            <span>
              Loss Terbesar:{" "}
              <strong className="text-rose-400 font-mono">
                {formatIdNumber(maxLossR, 2)} R
              </strong>
            </span>
            <span>
              Total Sample: <strong className="text-fg font-mono">{trades.length}</strong>
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
