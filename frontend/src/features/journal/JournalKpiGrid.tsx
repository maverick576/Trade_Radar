import React from "react";
import {
  Trophy,
  TrendingUp,
  TrendingDown,
  Target,
  Percent,
  Flame,
  ShieldAlert,
  DollarSign,
} from "lucide-react";
import type { JournalKPIs } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface JournalKpiGridProps {
  kpis: JournalKPIs | null;
  compareKpis?: JournalKPIs | null;
  book: "paper" | "real" | "compare";
  isLoading?: boolean;
}

export const JournalKpiGrid: React.FC<JournalKpiGridProps> = ({
  kpis,
  compareKpis,
  book,
  isLoading = false,
}) => {
  if (isLoading || !kpis) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {[...Array(7)].map((_, i) => (
          <div
            key={i}
            className="p-4 rounded-xl bg-surface border border-border animate-pulse h-24"
          />
        ))}
      </div>
    );
  }

  const isWinratePositive = kpis.winrate_pct >= 50;
  const isPnlPositive = kpis.total_realized_pnl_usd >= 0;
  const isExpectancyPositive = kpis.expectancy_r >= 0;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
      {/* 1. Winrate */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Winrate</span>
          <Percent className={`w-4 h-4 ${isWinratePositive ? "text-emerald-400" : "text-amber-400"}`} />
        </div>
        <div className="mt-2">
          <div className="flex items-baseline gap-1">
            <span className="text-xl font-bold font-mono text-fg">
              {formatIdNumber(kpis.winrate_pct, 1)}%
            </span>
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            {kpis.wins}W · {kpis.losses}L · {kpis.breakevens}BE
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className="font-mono font-semibold text-fg">
                {formatIdNumber(compareKpis.winrate_pct, 1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 2. Profit Factor */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Profit Factor</span>
          <Trophy className={`w-4 h-4 ${kpis.profit_factor >= 1.5 ? "text-emerald-400" : "text-muted"}`} />
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-fg">
            {kpis.profit_factor >= 999 ? "∞" : formatIdNumber(kpis.profit_factor, 2)}
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            Target: ≥ 1.50
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className="font-mono font-semibold text-fg">
                {compareKpis.profit_factor >= 999 ? "∞" : formatIdNumber(compareKpis.profit_factor, 2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Expectancy (R) */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Expectancy</span>
          <Target className={`w-4 h-4 ${isExpectancyPositive ? "text-emerald-400" : "text-rose-400"}`} />
        </div>
        <div className="mt-2">
          <div className={`text-xl font-bold font-mono ${isExpectancyPositive ? "text-emerald-400" : "text-rose-400"}`}>
            {isExpectancyPositive ? "+" : ""}{formatIdNumber(kpis.expectancy_r, 2)} R
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            W: +{formatIdNumber(kpis.avg_win_r, 2)}R · L: {formatIdNumber(kpis.avg_loss_r, 2)}R
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className={`font-mono font-semibold ${compareKpis.expectancy_r >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {compareKpis.expectancy_r >= 0 ? "+" : ""}{formatIdNumber(compareKpis.expectancy_r, 2)} R
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 4. Total Realized PnL ($) */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Realized PnL</span>
          <DollarSign className={`w-4 h-4 ${isPnlPositive ? "text-emerald-400" : "text-rose-400"}`} />
        </div>
        <div className="mt-2">
          <div className={`text-xl font-bold font-mono ${isPnlPositive ? "text-emerald-400" : "text-rose-400"}`}>
            {isPnlPositive ? "+" : ""}${formatIdNumber(kpis.total_realized_pnl_usd, 2)}
          </div>
          <div className="text-[11px] text-muted mt-0.5 font-mono">
            {kpis.total_realized_pnl_r >= 0 ? "+" : ""}{formatIdNumber(kpis.total_realized_pnl_r, 1)} R
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className={`font-mono font-semibold ${compareKpis.total_realized_pnl_usd >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ${formatIdNumber(compareKpis.total_realized_pnl_usd, 2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 5. Max Drawdown */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Max Drawdown</span>
          <ShieldAlert className="w-4 h-4 text-amber-400" />
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-amber-400">
            -{formatIdNumber(kpis.max_drawdown_pct, 1)}%
          </div>
          <div className="text-[11px] text-muted mt-0.5 font-mono">
            -{formatIdNumber(kpis.max_drawdown_r, 1)} R (${formatIdNumber(kpis.max_drawdown_usd, 1)})
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className="font-mono font-semibold text-amber-400">
                -{formatIdNumber(compareKpis.max_drawdown_pct, 1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 6. Streak (Win / Loss) */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Streaks</span>
          <Flame className="w-4 h-4 text-orange-400" />
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-fg flex items-baseline gap-2">
            <span className="text-emerald-400">{kpis.max_win_streak}W</span>
            <span className="text-muted text-sm font-normal">/</span>
            <span className="text-rose-400">{kpis.max_loss_streak}L</span>
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            Saat ini: {kpis.current_streak > 0 ? `+${kpis.current_streak}W` : kpis.current_streak < 0 ? `${kpis.current_streak}L` : "0"}
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className="font-mono font-semibold text-fg">
                {compareKpis.max_win_streak}W / {compareKpis.max_loss_streak}L
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 7. Total Trades */}
      <div className="p-3.5 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Total Trade</span>
          {kpis.total_trades > 0 ? (
            <TrendingUp className="w-4 h-4 text-accent" />
          ) : (
            <TrendingDown className="w-4 h-4 text-muted" />
          )}
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-fg">
            {kpis.total_trades}
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            Posisi Selesai
          </div>
          {book === "compare" && compareKpis && (
            <div className="text-[10px] mt-1 pt-1 border-t border-border/50 text-muted flex items-center justify-between">
              <span>Real:</span>
              <span className="font-mono font-semibold text-fg">
                {compareKpis.total_trades}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
