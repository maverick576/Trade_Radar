import React, { useState } from "react";
import { Clock, Info } from "lucide-react";
import type { HeatmapCell } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface JournalHeatmapProps {
  cells: HeatmapCell[];
  isLoading?: boolean;
}

const DAY_LABELS = [
  "Senin",
  "Selasa",
  "Rabu",
  "Kamis",
  "Jumat",
  "Sabtu",
  "Minggu",
];

export const JournalHeatmap: React.FC<JournalHeatmapProps> = ({
  cells,
  isLoading = false,
}) => {
  const [hoveredCell, setHoveredCell] = useState<HeatmapCell | null>(null);

  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-72 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat heatmap waktu trade...
      </div>
    );
  }

  // Build 7x24 lookup matrix: day_of_week (0..6) x hour_of_day (0..23)
  const cellMap = new Map<string, HeatmapCell>();
  cells.forEach((c) => {
    cellMap.set(`${c.day_of_week}-${c.hour_of_day}`, c);
  });

  // Calculate maximum absolute R for color scale
  let maxAbsR = 1.0;
  cells.forEach((c) => {
    const abs = Math.abs(c.net_r);
    if (abs > maxAbsR) maxAbsR = abs;
  });

  const getCellColor = (cell: HeatmapCell | undefined) => {
    if (!cell || cell.total_trades === 0) {
      return "bg-slate-800/30 border-slate-800/60 hover:border-slate-600";
    }

    const intensity = Math.min(1, Math.abs(cell.net_r) / maxAbsR);

    if (cell.net_r > 0) {
      if (intensity > 0.6) return "bg-emerald-500 text-black font-semibold border-emerald-400";
      if (intensity > 0.3) return "bg-emerald-600/80 text-white border-emerald-500/60";
      return "bg-emerald-900/60 text-emerald-200 border-emerald-700/50";
    } else if (cell.net_r < 0) {
      if (intensity > 0.6) return "bg-rose-500 text-white font-semibold border-rose-400";
      if (intensity > 0.3) return "bg-rose-600/80 text-white border-rose-500/60";
      return "bg-rose-900/60 text-rose-200 border-rose-700/50";
    }

    return "bg-slate-700/60 text-slate-300 border-slate-600";
  };

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-accent/10 text-accent">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Heatmap Jam & Hari (WIB)</h3>
            <p className="text-xs text-muted">
              Distribusi performa net R berdasarkan waktu eksekusi candle entry (WIB)
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-rose-500 inline-block" /> Loss
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-slate-800/60 border border-slate-700 inline-block" /> 0
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-emerald-500 inline-block" /> Profit
          </span>
        </div>
      </div>

      {/* Grid Table */}
      <div className="overflow-x-auto select-none">
        <div className="min-w-[700px]">
          {/* Hour header (00..23) */}
          <div className="grid grid-cols-[60px_repeat(24,1fr)] gap-1 mb-1 text-[10px] font-mono text-muted text-center">
            <div />
            {Array.from({ length: 24 }).map((_, h) => (
              <div key={h} className={h % 4 === 0 ? "font-bold text-fg" : ""}>
                {h.toString().padStart(2, "0")}
              </div>
            ))}
          </div>

          {/* Days rows */}
          <div className="flex flex-col gap-1">
            {DAY_LABELS.map((dayName, dayIdx) => (
              <div
                key={dayIdx}
                className="grid grid-cols-[60px_repeat(24,1fr)] gap-1 items-center"
              >
                <div className="text-[11px] font-medium text-muted truncate pr-2 text-right">
                  {dayName.slice(0, 3)}
                </div>

                {Array.from({ length: 24 }).map((_, hour) => {
                  const cell = cellMap.get(`${dayIdx}-${hour}`);
                  const colorClass = getCellColor(cell);

                  return (
                    <div
                      key={hour}
                      onMouseEnter={() =>
                        setHoveredCell(
                          cell || {
                            day_of_week: dayIdx,
                            hour_of_day: hour,
                            total_trades: 0,
                            wins: 0,
                            losses: 0,
                            winrate_pct: 0,
                            net_r: 0,
                            net_pnl_usd: 0,
                          }
                        )
                      }
                      onMouseLeave={() => setHoveredCell(null)}
                      className={`h-6 rounded border transition-all cursor-pointer flex items-center justify-center text-[9px] ${colorClass}`}
                    >
                      {cell && cell.total_trades > 0 && (
                        <span>{cell.total_trades}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          {/* Sessions indicator bar */}
          <div className="grid grid-cols-[60px_repeat(24,1fr)] gap-1 mt-2 text-[9px] text-muted text-center">
            <div />
            <div className="col-span-8 bg-blue-500/10 border border-blue-500/30 rounded py-0.5 text-blue-400">
              Asia (00-08 UTC / 07-15 WIB)
            </div>
            <div className="col-span-8 bg-amber-500/10 border border-amber-500/30 rounded py-0.5 text-amber-400">
              London (08-16 UTC / 15-23 WIB)
            </div>
            <div className="col-span-8 bg-purple-500/10 border border-purple-500/30 rounded py-0.5 text-purple-400">
              New York (13-21 UTC / 20-04 WIB)
            </div>
          </div>
        </div>
      </div>

      {/* Hover Info Footer */}
      <div className="min-h-[28px] text-xs font-mono bg-surface-hover/50 rounded-lg p-2 flex items-center justify-between border border-border/40">
        {hoveredCell ? (
          <>
            <div>
              <span className="text-muted">Waktu: </span>
              <strong className="text-fg">
                {DAY_LABELS[hoveredCell.day_of_week]}, {hoveredCell.hour_of_day.toString().padStart(2, "0")}:00 WIB
              </strong>
            </div>
            <div>
              <span className="text-muted">Total Trade: </span>
              <strong className="text-fg">{hoveredCell.total_trades}</strong>{" "}
              ({hoveredCell.wins}W / {hoveredCell.losses}L · {formatIdNumber(hoveredCell.winrate_pct, 1)}%)
            </div>
            <div>
              <span className="text-muted">Hasil Net: </span>
              <strong
                className={
                  hoveredCell.net_r >= 0 ? "text-emerald-400" : "text-rose-400"
                }
              >
                {hoveredCell.net_r >= 0 ? "+" : ""}
                {formatIdNumber(hoveredCell.net_r, 2)} R (${formatIdNumber(hoveredCell.net_pnl_usd, 2)})
              </strong>
            </div>
          </>
        ) : (
          <div className="text-muted text-[11px] flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5" />
            Arahkan mouse ke kotak heatmap untuk melihat detail performa jam tersebut.
          </div>
        )}
      </div>
    </div>
  );
};
