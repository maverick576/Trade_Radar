import React, { useState, useEffect } from "react";
import {
  Clock,
  Copy,
  Check,
  CheckCircle2,
  Sliders,
  AlertTriangle,
  Info,
  ShieldAlert,
  ChevronRight,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import type { TicketItem } from "../../api/client";
import {
  formatIdNumber,
  formatCountdown,
  copyToClipboard,
  buildCompactCopyString,
} from "./formatTicket";
import { CalibrationDialog } from "./CalibrationDialog";
import { ExecutionDialog } from "./ExecutionDialog";
import { CloseExecutionDialog } from "./CloseExecutionDialog";

interface TicketCardProps {
  ticket: TicketItem;
  onRefresh?: () => void;
  compactMode?: boolean;
}

export const TicketCard: React.FC<TicketCardProps> = ({
  ticket,
  onRefresh,
  compactMode = false,
}) => {
  const [countdown, setCountdown] = useState(formatCountdown(ticket.valid_until));
  const [copiedType, setCopiedType] = useState<"full" | "compact" | null>(null);

  // Dialogs
  const [calibrationOpen, setCalibrationOpen] = useState<boolean>(false);
  const [executionOpen, setExecutionOpen] = useState<boolean>(false);
  const [closeExecutionOpen, setCloseExecutionOpen] = useState<boolean>(false);

  // Update countdown every second
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown(formatCountdown(ticket.valid_until));
    }, 1000);
    return () => clearInterval(timer);
  }, [ticket.valid_until]);

  const isLong = ticket.side === "LONG";
  const isExpired = countdown.isExpired || ticket.status === "expired";
  const isExecuted = ticket.status === "executed";
  const isClosed = ticket.status === "closed";
  const isSkipped = ticket.status === "skipped";

  const handleCopyFull = async () => {
    const text = ticket.text_full || "";
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopiedType("full");
      setTimeout(() => setCopiedType(null), 2000);
    }
  };

  const handleCopyCompact = async () => {
    const text = buildCompactCopyString(ticket);
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopiedType("compact");
      setTimeout(() => setCopiedType(null), 2000);
    }
  };

  const dec = ticket.symbol.startsWith("XAU") || ticket.symbol.startsWith("BTC") ? 1 : 2;

  return (
    <div
      className={`rounded-xl border transition-all duration-200 overflow-hidden ${
        isExecuted
          ? "bg-surface border-bull/40 shadow-lg shadow-bull/5"
          : isClosed
          ? "bg-surface/60 border-border opacity-75"
          : isSkipped || isExpired
          ? "bg-surface/50 border-border opacity-60"
          : isLong
          ? "bg-surface border-bull/30 shadow-lg shadow-bull/5 hover:border-bull/50"
          : "bg-surface border-bear/30 shadow-lg shadow-bear/5 hover:border-bear/50"
      }`}
    >
      {/* Top Banner / Header */}
      <div className="p-4 border-b border-border/80 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs ${
              isLong ? "bg-bull/20 text-bull" : "bg-bear/20 text-bear"
            }`}
          >
            {isLong ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-sm font-black tracking-wide ${isLong ? "text-bull" : "text-bear"}`}>
                {isLong ? "BUY" : "SELL"} {ticket.symbol}
              </span>
              <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-surface-2 text-muted border border-border">
                M15
              </span>
              <span className="text-[11px] font-semibold text-fg">
                {ticket.strategy}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted mt-0.5">
              <span>Skor: <strong className={ticket.score >= 55 ? "text-bull" : "text-bear"}>{Math.round(ticket.score)}</strong></span>
              <span>•</span>
              <span>{ticket.source}</span>
              {ticket.broker_offset ? (
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-accent/15 text-accent border border-accent/30 font-mono">
                  Offset {ticket.broker_offset > 0 ? "+" : ""}{formatIdNumber(ticket.broker_offset, 1)}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Status / Countdown Badge */}
        <div className="flex items-center gap-2">
          {isExecuted ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-bull/20 text-bull border border-bull/40 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> Posisi Terbuka (Real)
            </span>
          ) : isClosed ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-surface-2 text-muted border border-border">
              Selesai Ditutup
            </span>
          ) : isSkipped ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-surface-2 text-muted border border-border">
              Dilewati
            </span>
          ) : isExpired ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-bear/15 text-bear border border-bear/30">
              Kedaluwarsa
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-warn/15 text-warn border border-warn/30 flex items-center gap-1.5 animate-pulse">
              <Clock className="w-3.5 h-3.5" /> {countdown.text}
            </span>
          )}
        </div>
      </div>

      {/* Levels Table */}
      <div className="p-4 space-y-3">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-border/60 text-muted font-medium text-[11px]">
                <th className="pb-1.5">Level</th>
                <th className="pb-1.5 font-mono">Harga Sumber</th>
                <th className="pb-1.5 font-mono">Harga Broker</th>
                <th className="pb-1.5 text-right font-mono">Jarak (R)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 font-mono">
              {/* Entry Row */}
              <tr>
                <td className="py-1.5 text-fg font-sans font-semibold flex items-center gap-1">
                  Entry
                  <span className="text-[10px] text-muted font-normal">
                    (zona {formatIdNumber(ticket.entry_low, dec)} – {formatIdNumber(ticket.entry_high, dec)})
                  </span>
                </td>
                <td className="py-1.5 text-fg font-bold">{formatIdNumber(ticket.entry, dec)}</td>
                <td className="py-1.5 text-fg">
                  {ticket.broker_offset
                    ? formatIdNumber(ticket.entry + ticket.broker_offset, dec)
                    : formatIdNumber(ticket.entry, dec)}
                </td>
                <td className="py-1.5 text-right text-muted">Market Zona</td>
              </tr>

              {/* SL Row */}
              <tr className="text-bear">
                <td className="py-1.5 font-sans font-semibold">Stop Loss (SL)</td>
                <td className="py-1.5 font-bold">{formatIdNumber(ticket.sl, dec)}</td>
                <td className="py-1.5">
                  {ticket.broker_offset
                    ? formatIdNumber(ticket.sl + ticket.broker_offset, dec)
                    : formatIdNumber(ticket.sl, dec)}
                </td>
                <td className="py-1.5 text-right">
                  −{formatIdNumber(ticket.sl_points, dec)} ({formatIdNumber(ticket.sl_atr_mult, 1)}×ATR)
                </td>
              </tr>

              {/* TP1 Row */}
              <tr className="text-bull">
                <td className="py-1.5 font-sans font-semibold flex items-center gap-1">
                  TP1 <span className="text-[10px] text-muted">(tutup 50% & SL→BE)</span>
                </td>
                <td className="py-1.5 font-bold">{formatIdNumber(ticket.tp1, dec)}</td>
                <td className="py-1.5">
                  {ticket.broker_offset
                    ? formatIdNumber(ticket.tp1 + ticket.broker_offset, dec)
                    : formatIdNumber(ticket.tp1, dec)}
                </td>
                <td className="py-1.5 text-right">+1,0R</td>
              </tr>

              {/* TP2 Row */}
              <tr className="text-bull">
                <td className="py-1.5 font-sans font-semibold">TP2 (Target Sisa)</td>
                <td className="py-1.5 font-bold">{formatIdNumber(ticket.tp2, dec)}</td>
                <td className="py-1.5">
                  {ticket.broker_offset
                    ? formatIdNumber(ticket.tp2 + ticket.broker_offset, dec)
                    : formatIdNumber(ticket.tp2, dec)}
                </td>
                <td className="py-1.5 text-right">+2,0R</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Lot & Broker Calculator */}
        <div className="p-2.5 rounded-lg bg-surface-2/60 border border-border text-xs flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-muted font-medium">Saran Lot:</span>
              <span className="font-mono font-bold text-fg">
                {ticket.suggested_lot ? `${formatIdNumber(ticket.suggested_lot, 2)} lot` : "0,06 lot"}
              </span>
              <span className="text-muted text-[11px]">
                ({ticket.broker_profile || "Exness Standard"})
              </span>
            </div>
            <div className="text-[11px] text-muted mt-0.5">
              Risiko 1% dari $10.000 = $100 → aktual ${ticket.actual_risk_usd ? Math.round(ticket.actual_risk_usd) : 87} ({ticket.actual_risk_pct || 0.87}%)
            </div>
          </div>

          <button
            onClick={() => setCalibrationOpen(true)}
            className="px-2 py-1 rounded text-[11px] font-medium bg-surface hover:bg-surface-2 border border-border text-accent flex items-center gap-1 transition-colors"
          >
            <Sliders className="w-3 h-3" /> Kalibrasi Harga Broker
          </button>
        </div>

        {ticket.min_lot_warning && ticket.warning_message && (
          <div className="p-2 rounded bg-bear/10 border border-bear/30 text-bear text-xs flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>{ticket.warning_message}</span>
          </div>
        )}

        {/* Invalidation Alert */}
        <div className="p-2.5 rounded-lg bg-warn/10 border border-warn/30 text-warn text-xs flex items-start gap-2">
          <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold text-warn">Kondisi Invalidasi:</strong>{" "}
            <span className="text-fg/90">{ticket.invalidation}</span>
          </div>
        </div>

        {/* Reasons & Risks */}
        {!compactMode && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs pt-1">
            <div className="p-2.5 rounded-lg bg-surface-2/40 border border-border">
              <div className="text-[11px] font-semibold text-bull mb-1 flex items-center gap-1">
                <Info className="w-3.5 h-3.5" /> Konfluensi Alasan
              </div>
              <ul className="space-y-1 text-muted text-[11px] list-disc list-inside">
                {ticket.reasons?.length ? (
                  ticket.reasons.map((r, i) => <li key={i}>{r}</li>)
                ) : (
                  <li>EMA ribbon & Supertrend bullish · CVD naik · Di atas VWAP</li>
                )}
              </ul>
            </div>

            <div className="p-2.5 rounded-lg bg-surface-2/40 border border-border">
              <div className="text-[11px] font-semibold text-warn mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Perhatian Risiko
              </div>
              <ul className="space-y-1 text-muted text-[11px] list-disc list-inside">
                {ticket.risks?.length ? (
                  ticket.risks.map((r, i) => <li key={i}>{r}</li>)
                ) : (
                  <li>RSI mendekati overbought · Waspada rilis data makro</li>
                )}
              </ul>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="pt-2 border-t border-border/60 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCopyFull}
              className="px-2.5 py-1.5 rounded-lg bg-surface-2 hover:bg-surface-2/80 border border-border text-xs font-medium text-fg flex items-center gap-1.5 transition-colors"
              title="Salin teks lengkap tiket"
            >
              {copiedType === "full" ? (
                <>
                  <Check className="w-3.5 h-3.5 text-bull" />
                  <span className="text-bull">Tersalin!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-muted" />
                  <span>Salin Lengkap</span>
                </>
              )}
            </button>

            <button
              onClick={handleCopyCompact}
              className="px-2.5 py-1.5 rounded-lg bg-surface-2 hover:bg-surface-2/80 border border-border text-xs font-medium text-fg flex items-center gap-1.5 transition-colors"
              title="Salin satu baris ringkas: BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot"
            >
              {copiedType === "compact" ? (
                <>
                  <Check className="w-3.5 h-3.5 text-bull" />
                  <span className="text-bull">Tersalin!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-muted" />
                  <span>Salin Ringkas</span>
                </>
              )}
            </button>
          </div>

          <div className="flex items-center gap-2">
            {isExecuted ? (
              <button
                onClick={() => setCloseExecutionOpen(true)}
                className="px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-bold hover:bg-accent/90 transition-colors flex items-center gap-1"
              >
                Tutup Posisi Real <ChevronRight className="w-3.5 h-3.5" />
              </button>
            ) : !isClosed && !isSkipped ? (
              <button
                onClick={() => setExecutionOpen(true)}
                className="px-3 py-1.5 rounded-lg bg-bull text-white text-xs font-bold hover:bg-bull/90 transition-colors flex items-center gap-1 shadow-sm"
              >
                Saya Eksekusi <ChevronRight className="w-3.5 h-3.5" />
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* Modals */}
      <CalibrationDialog
        isOpen={calibrationOpen}
        onClose={() => setCalibrationOpen(false)}
        symbol={ticket.symbol}
        sourcePrice={ticket.entry}
        currentOffset={ticket.broker_offset}
        onCalibrationSaved={onRefresh}
      />

      <ExecutionDialog
        isOpen={executionOpen}
        onClose={() => setExecutionOpen(false)}
        ticket={ticket}
        onExecutionRecorded={onRefresh}
      />

      <CloseExecutionDialog
        isOpen={closeExecutionOpen}
        onClose={() => setCloseExecutionOpen(false)}
        ticket={ticket}
        onClosed={onRefresh}
      />
    </div>
  );
};
