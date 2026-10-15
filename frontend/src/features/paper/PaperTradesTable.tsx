import React, { useState } from "react";
import {
  TrendingUp,
  TrendingDown,
  XCircle,
  Clock,
  Layers,
  Sparkles,
} from "lucide-react";
import type { PaperTradeItem } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface PaperTradesTableProps {
  trades: PaperTradeItem[];
  onCloseTrade?: (tradeId: number, currentPrice: number) => void;
  isLoading?: boolean;
}

export const PaperTradesTable: React.FC<PaperTradesTableProps> = ({
  trades,
  onCloseTrade,
  isLoading = false,
}) => {
  const [filterTab, setFilterTab] = useState<"ALL" | "OPEN" | "CLOSED" | "VIRTUAL">("ALL");

  const filtered = trades.filter((t) => {
    if (filterTab === "OPEN") return t.status === "OPEN" && !t.is_virtual;
    if (filterTab === "CLOSED") return t.status === "CLOSED" && !t.is_virtual;
    if (filterTab === "VIRTUAL") return t.is_virtual;
    return true;
  });

  if (isLoading) {
    return (
      <div className="p-8 text-center text-muted bg-surface rounded-xl border border-border">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <span className="text-sm">Memuat data posisi paper trading...</span>
      </div>
    );
  }

  const renderExitBadge = (reason: string | null | undefined) => {
    if (!reason) return <span className="text-muted">-</span>;
    switch (reason) {
      case "TP1":
      case "TP2":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-bull/20 text-bull border border-bull/30">
            {reason}
          </span>
        );
      case "BE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-accent/20 text-accent border border-accent/30">
            BE (Breakeven)
          </span>
        );
      case "SL":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-bear/20 text-bear border border-bear/30">
            SL
          </span>
        );
      case "TIME_STOP":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-surface-2 text-muted border border-border">
            Time Stop (32 Bar)
          </span>
        );
      case "OPPOSITE_SIGNAL":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-warn/20 text-warn border border-warn/30">
            Sinyal Berlawanan
          </span>
        );
      case "MANUAL":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-surface-2 text-fg border border-border">
            Tutup Manual
          </span>
        );
      default:
        return <span className="text-muted text-xs">{reason}</span>;
    }
  };

  return (
    <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden">
      {/* Table Header & Tabs */}
      <div className="p-4 border-b border-border flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-accent" />
          <h3 className="text-sm font-bold text-fg">Jurnal & Posisi Paper Trading</h3>
          <span className="text-xs text-muted font-mono">({filtered.length} posisi)</span>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 bg-surface-2 p-1 rounded-lg border border-border text-xs">
          <button
            onClick={() => setFilterTab("ALL")}
            className={`px-3 py-1 rounded-md transition-colors ${
              filterTab === "ALL"
                ? "bg-surface text-fg font-semibold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            Semua
          </button>
          <button
            onClick={() => setFilterTab("OPEN")}
            className={`px-3 py-1 rounded-md transition-colors flex items-center gap-1.5 ${
              filterTab === "OPEN"
                ? "bg-surface text-bull font-semibold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-bull" />
            Terbuka
          </button>
          <button
            onClick={() => setFilterTab("CLOSED")}
            className={`px-3 py-1 rounded-md transition-colors ${
              filterTab === "CLOSED"
                ? "bg-surface text-fg font-semibold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            Riwayat Selesai
          </button>
          <button
            onClick={() => setFilterTab("VIRTUAL")}
            className={`px-3 py-1 rounded-md transition-colors flex items-center gap-1 ${
              filterTab === "VIRTUAL"
                ? "bg-surface text-warn font-semibold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            <Sparkles className="w-3 h-3 text-warn" />
            Simulasi Virtual
          </button>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-border text-muted font-medium bg-surface-2/40 text-[11px]">
              <th className="py-2.5 px-4">Simbol & Sisi</th>
              <th className="py-2.5 px-3">Strategi</th>
              <th className="py-2.5 px-3 font-mono">Entry</th>
              <th className="py-2.5 px-3 font-mono">Current SL</th>
              <th className="py-2.5 px-3 font-mono">Target TP</th>
              <th className="py-2.5 px-3 font-mono">Ukuran / Bar</th>
              <th className="py-2.5 px-3">Exit & Alasan</th>
              <th className="py-2.5 px-4 text-right font-mono">PnL (USD & R)</th>
              <th className="py-2.5 px-3 text-center">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 font-mono">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-12 text-center text-muted font-sans text-xs">
                  Tidak ada posisi paper trading pada filter ini.
                </td>
              </tr>
            ) : (
              filtered.map((t) => {
                const isLong = t.side === "LONG";
                const isOpen = t.status === "OPEN";
                const dec = t.symbol.startsWith("XAU") || t.symbol.startsWith("BTC") ? 1 : 2;

                return (
                  <tr
                    key={t.id}
                    className={`hover:bg-surface-2/40 transition-colors ${
                      t.is_virtual ? "opacity-75" : ""
                    }`}
                  >
                    {/* Simbol & Sisi */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2 font-sans font-bold">
                        <span
                          className={`w-5 h-5 rounded flex items-center justify-center text-[10px] ${
                            isLong ? "bg-bull/20 text-bull" : "bg-bear/20 text-bear"
                          }`}
                        >
                          {isLong ? (
                            <TrendingUp className="w-3.5 h-3.5" />
                          ) : (
                            <TrendingDown className="w-3.5 h-3.5" />
                          )}
                        </span>
                        <div>
                          <div className="text-fg flex items-center gap-1.5">
                            <span>{t.symbol}</span>
                            <span className={isLong ? "text-bull text-xs" : "text-bear text-xs"}>
                              {isLong ? "BUY" : "SELL"}
                            </span>
                          </div>
                          {t.is_virtual && (
                            <span className="text-[10px] text-warn font-normal flex items-center gap-0.5">
                              <Sparkles className="w-2.5 h-2.5" /> Sinyal Terblokir (Virtual)
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Strategi */}
                    <td className="py-3 px-3 font-sans text-muted text-xs">
                      {t.strategy}
                    </td>

                    {/* Entry */}
                    <td className="py-3 px-3 text-fg font-semibold">
                      {formatIdNumber(t.entry_price, dec)}
                    </td>

                    {/* SL */}
                    <td className="py-3 px-3 text-bear">
                      <div className="flex items-center gap-1">
                        <span>{formatIdNumber(t.sl, dec)}</span>
                        {t.tp1_hit && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-accent/20 text-accent font-sans">
                            BE
                          </span>
                        )}
                      </div>
                    </td>

                    {/* TP */}
                    <td className="py-3 px-3 text-bull">
                      <div className="text-xs">
                        <span>TP1: {formatIdNumber(t.tp1, dec)}</span>
                        <div className="text-[10px] text-muted font-normal">
                          TP2: {formatIdNumber(t.tp2, dec)}
                        </div>
                      </div>
                    </td>

                    {/* Size & Bars */}
                    <td className="py-3 px-3 text-fg text-xs">
                      <div>{t.size.toFixed(dec === 1 ? 2 : 4)} unit</div>
                      <div className="text-[10px] text-muted flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {t.bars_held} bar
                      </div>
                    </td>

                    {/* Exit & Alasan */}
                    <td className="py-3 px-3">
                      {isOpen ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-bull/15 text-bull border border-bull/30 flex items-center gap-1 w-max">
                          <span className="w-1.5 h-1.5 rounded-full bg-bull animate-ping" />
                          Aktif Berjalan
                        </span>
                      ) : (
                        <div className="space-y-0.5">
                          <div className="font-semibold text-fg">
                            {t.exit_price ? formatIdNumber(t.exit_price, dec) : "-"}
                          </div>
                          <div>{renderExitBadge(t.exit_reason)}</div>
                        </div>
                      )}
                    </td>

                    {/* PnL */}
                    <td className="py-3 px-4 text-right">
                      {isOpen ? (
                        <div className="text-muted text-xs">Floating...</div>
                      ) : (
                        <div
                          className={`font-bold ${
                            (t.pnl_usd || 0) >= 0 ? "text-bull" : "text-bear"
                          }`}
                        >
                          <div>
                            {(t.pnl_usd || 0) >= 0 ? "+" : ""}
                            ${formatIdNumber(t.pnl_usd || 0, 2)}
                          </div>
                          <div className="text-[11px] font-normal opacity-90">
                            {(t.pnl_r || 0) >= 0 ? "+" : ""}
                            {(t.pnl_r || 0).toFixed(2)}R
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Aksi */}
                    <td className="py-3 px-3 text-center">
                      {isOpen && onCloseTrade && (
                        <button
                          onClick={() => onCloseTrade(t.id, t.entry_price)}
                          className="p-1 rounded hover:bg-surface-2 text-muted hover:text-bear transition-colors"
                          title="Tutup posisi manual"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
