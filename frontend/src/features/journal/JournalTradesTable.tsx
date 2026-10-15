import React, { useState, useMemo } from "react";
import {
  Search,
  Eye,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import type { TradeRecordItem } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface JournalTradesTableProps {
  trades: TradeRecordItem[];
  onSelectTrade: (tradeId: string) => void;
  isLoading?: boolean;
}

export const JournalTradesTable: React.FC<JournalTradesTableProps> = ({
  trades,
  onSelectTrade,
  isLoading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterOutcome, setFilterOutcome] = useState<string>("ALL");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  // Filter trades
  const filtered = useMemo(() => {
    return trades.filter((t) => {
      if (filterOutcome !== "ALL" && t.outcome !== filterOutcome) {
        return false;
      }
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        t.symbol.toLowerCase().includes(term) ||
        t.side.toLowerCase().includes(term) ||
        (t.strategy && t.strategy.toLowerCase().includes(term)) ||
        (t.exit_reason && t.exit_reason.toLowerCase().includes(term)) ||
        t.book.toLowerCase().includes(term)
      );
    });
  }, [trades, searchTerm, filterOutcome]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginatedTrades = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, currentPage, pageSize]);

  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-64 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat daftar trade...
      </div>
    );
  }

  const formatWibDate = (isoStr: string | null | undefined) => {
    if (!isoStr) return "-";
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("id-ID", {
        timeZone: "Asia/Jakarta",
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header & Search Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-fg">Riwayat Posisi & Eksekusi ({trades.length})</h3>
          <p className="text-xs text-muted">
            Daftar lengkap posisi tertutup beserta snapshot kondisi teknikal saat entry
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Search box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Cari simbol, alasan, strategi..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="pl-8 pr-3 py-1.5 rounded-lg bg-surface-hover border border-border text-xs text-fg focus:outline-none focus:border-accent w-48 sm:w-56"
            />
          </div>

          {/* Outcome Filter */}
          <select
            value={filterOutcome}
            onChange={(e) => {
              setFilterOutcome(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 rounded-lg bg-surface-hover border border-border text-xs text-fg focus:outline-none focus:border-accent"
          >
            <option value="ALL">Semua Hasil</option>
            <option value="WIN">Win</option>
            <option value="LOSS">Loss</option>
            <option value="BREAKEVEN">Breakeven</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="py-12 text-center text-muted text-xs">
          Tidak ada trade yang sesuai dengan pencarian atau filter.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted font-mono">
                <th className="py-2.5 px-3 font-medium">Waktu Entry (WIB)</th>
                <th className="py-2.5 px-3 font-medium">Buku</th>
                <th className="py-2.5 px-3 font-medium">Simbol</th>
                <th className="py-2.5 px-3 font-medium">Arah</th>
                <th className="py-2.5 px-3 font-medium">Strategi</th>
                <th className="py-2.5 px-3 font-medium text-right">Entry</th>
                <th className="py-2.5 px-3 font-medium text-right">Exit</th>
                <th className="py-2.5 px-3 font-medium text-right">Lot</th>
                <th className="py-2.5 px-3 font-medium text-center">Alasan</th>
                <th className="py-2.5 px-3 font-medium text-right">PnL (R)</th>
                <th className="py-2.5 px-3 font-medium text-right">PnL ($)</th>
                <th className="py-2.5 px-3 font-medium text-center">Snapshot</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30 font-mono">
              {paginatedTrades.map((t) => {
                const isPnlPositive = t.pnl_usd >= 0;

                return (
                  <tr key={t.id} className="hover:bg-surface-hover/50 transition-colors">
                    {/* Waktu Entry */}
                    <td className="py-2.5 px-3 text-fg whitespace-nowrap">
                      {formatWibDate(t.entry_time)}
                    </td>

                    {/* Buku */}
                    <td className="py-2.5 px-3 font-sans">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          t.book === "real"
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                        }`}
                      >
                        {t.book}
                      </span>
                    </td>

                    {/* Simbol */}
                    <td className="py-2.5 px-3 font-bold text-fg">{t.symbol}</td>

                    {/* Arah */}
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          t.side === "LONG"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : "bg-rose-500/15 text-rose-400"
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>

                    {/* Strategi */}
                    <td className="py-2.5 px-3 text-muted text-[11px] font-sans">
                      {t.strategy || "A"}
                    </td>

                    {/* Entry Price */}
                    <td className="py-2.5 px-3 text-right text-fg">
                      {t.entry_price}
                      {t.slippage_points ? (
                        <span
                          className="block text-[9px] text-amber-400"
                          title="Slippage vs ticket"
                        >
                          +{formatIdNumber(t.slippage_points, 1)}pt
                        </span>
                      ) : null}
                    </td>

                    {/* Exit Price */}
                    <td className="py-2.5 px-3 text-right text-fg">
                      {t.exit_price || "-"}
                    </td>

                    {/* Lot */}
                    <td className="py-2.5 px-3 text-right text-muted">{t.lot}</td>

                    {/* Exit Reason */}
                    <td className="py-2.5 px-3 text-center">
                      <span className="px-1.5 py-0.5 rounded bg-surface-hover text-[10px] text-muted">
                        {t.exit_reason || "-"}
                      </span>
                    </td>

                    {/* PnL R */}
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        t.pnl_r >= 0 ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {t.pnl_r >= 0 ? "+" : ""}
                      {formatIdNumber(t.pnl_r, 2)} R
                    </td>

                    {/* PnL USD */}
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        isPnlPositive ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {isPnlPositive ? "+" : ""}${formatIdNumber(t.pnl_usd, 2)}
                    </td>

                    {/* Snapshot Action */}
                    <td className="py-2.5 px-3 text-center">
                      <button
                        type="button"
                        onClick={() => onSelectTrade(t.id)}
                        className="p-1 rounded-md text-muted hover:text-accent hover:bg-surface transition-colors"
                        title="Buka Snapshot Analisa Sinyal"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border/50 pt-3 text-xs text-muted">
          <div>
            Menampilkan {(currentPage - 1) * pageSize + 1}–
            {Math.min(currentPage * pageSize, filtered.length)} dari {filtered.length} trade
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-md border border-border bg-surface text-fg hover:bg-surface-hover disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span className="px-2 font-mono">
              Halaman {currentPage} / {totalPages}
            </span>

            <button
              type="button"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-md border border-border bg-surface text-fg hover:bg-surface-hover disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
