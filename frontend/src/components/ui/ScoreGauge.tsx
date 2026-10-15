import React from "react";
import { TrendingUp, TrendingDown, Minus, ShieldAlert } from "lucide-react";

interface ScoreGaugeProps {
  score: number; // -100 to +100
  verdict: string; // STRONG_LONG, LONG, NEUTRAL, SHORT, STRONG_SHORT
  counts?: Record<string, number>;
  availableWeightPct?: number;
  compact?: boolean;
}

export const ScoreGauge: React.FC<ScoreGaugeProps> = ({
  score,
  verdict,
  counts,
  availableWeightPct = 100,
  compact = false,
}) => {
  // Normalize -100..+100 to 0..100% for progress / gauge positioning
  const clampedScore = Math.max(-100, Math.min(100, score));
  const normalizedPct = ((clampedScore + 100) / 200) * 100;

  const isBull = score > 15;
  const isBear = score < -15;

  const getVerdictBadge = (v: string) => {
    switch (v) {
      case "STRONG_LONG":
        return {
          label: "STRONG BUY",
          bg: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
          icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
        };
      case "LONG":
        return {
          label: "BUY (PANTAU)",
          bg: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
          icon: <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />,
        };
      case "STRONG_SHORT":
        return {
          label: "STRONG SELL",
          bg: "bg-rose-500/20 text-rose-400 border-rose-500/40",
          icon: <TrendingDown className="w-4 h-4 text-rose-400" />,
        };
      case "SHORT":
        return {
          label: "SELL (PANTAU)",
          bg: "bg-rose-500/15 text-rose-400 border-rose-500/30",
          icon: <TrendingDown className="w-3.5 h-3.5 text-rose-400" />,
        };
      default:
        return {
          label: "NETRAL",
          bg: "bg-surface-2 text-muted border-border",
          icon: <Minus className="w-3.5 h-3.5 text-muted" />,
        };
    }
  };

  const badge = getVerdictBadge(verdict);

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <div className="w-16 h-2 bg-surface-2 rounded-full overflow-hidden border border-border relative">
          <div
            className={`h-full transition-all duration-500 ${
              isBull ? "bg-emerald-500" : isBear ? "bg-rose-500" : "bg-neutral"
            }`}
            style={{ width: `${Math.max(normalizedPct, 8)}%` }}
          />
        </div>
        <span
          className={`font-mono text-xs font-bold ${
            isBull ? "text-emerald-400" : isBear ? "text-rose-400" : "text-muted"
          }`}
        >
          {score > 0 ? `+${score.toFixed(0)}` : score.toFixed(0)}
        </span>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold uppercase tracking-wider text-muted font-mono">
          Skor Konfluensi
        </span>
        <div
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold font-mono border ${badge.bg}`}
        >
          {badge.icon}
          <span>{badge.label}</span>
        </div>
      </div>

      {/* Numerical Score Display */}
      <div className="flex items-baseline justify-between my-2">
        <div>
          <span
            className={`text-3xl font-extrabold font-mono tracking-tight ${
              isBull ? "text-emerald-400" : isBear ? "text-rose-400" : "text-fg"
            }`}
          >
            {score > 0 ? `+${score.toFixed(1)}` : score.toFixed(1)}
          </span>
          <span className="text-xs text-muted font-mono ml-1.5">/ ±100</span>
        </div>

        {counts && (
          <div className="flex items-center gap-2 text-xs font-mono font-semibold">
            <span className="text-emerald-400 flex items-center gap-0.5">
              ▲ {counts.BULL}
            </span>
            <span className="text-muted flex items-center gap-0.5">
              • {counts.NEUTRAL}
            </span>
            <span className="text-rose-400 flex items-center gap-0.5">
              ▼ {counts.BEAR}
            </span>
            {counts.NA > 0 && (
              <span className="text-muted/60 text-[10px]">({counts.NA} NA)</span>
            )}
          </div>
        )}
      </div>

      {/* Visual Linear Gauge with Center Point */}
      <div className="space-y-1.5 mt-2">
        <div className="relative w-full h-3 bg-surface-2 rounded-full overflow-hidden border border-border">
          {/* Neutral center marker */}
          <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-border z-10" />

          {/* Fill Bar starting from center (50%) */}
          {clampedScore >= 0 ? (
            <div
              className="absolute top-0 bottom-0 left-1/2 bg-emerald-500 transition-all duration-500 rounded-r-full"
              style={{ width: `${(clampedScore / 100) * 50}%` }}
            />
          ) : (
            <div
              className="absolute top-0 bottom-0 right-1/2 bg-rose-500 transition-all duration-500 rounded-l-full"
              style={{ width: `${(Math.abs(clampedScore) / 100) * 50}%` }}
            />
          )}
        </div>

        <div className="flex justify-between text-[10px] font-mono text-muted">
          <span>-100 (Bearish)</span>
          <span>0 (Netral)</span>
          <span>+100 (Bullish)</span>
        </div>
      </div>

      {/* Available Weights Warning if < 50% */}
      {availableWeightPct < 50 && (
        <div className="mt-3 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-500 text-[11px] flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 flex-shrink-0" />
          <span>
            Bobot tersedia <strong>{availableWeightPct}%</strong> &lt; 50%: verdict dibatasi ke pantau (tidak boleh STRONG).
          </span>
        </div>
      )}
    </div>
  );
};
