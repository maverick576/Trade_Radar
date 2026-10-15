import React, { useState } from "react";
import { CheckCircle2, X, AlertCircle } from "lucide-react";
import { apiClient, type TicketItem } from "../../api/client";

interface ExecutionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  ticket: TicketItem;
  onExecutionRecorded?: () => void;
}

export const ExecutionDialog: React.FC<ExecutionDialogProps> = ({
  isOpen,
  onClose,
  ticket,
  onExecutionRecorded,
}) => {
  const [fillPrice, setFillPrice] = useState<string>(ticket.entry.toString());
  const [lot, setLot] = useState<string>((ticket.suggested_lot || 0.01).toString());
  const [brokerProfile, setBrokerProfile] = useState<string>(
    ticket.broker_profile || "Exness Standard"
  );
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const numFillPrice = parseFloat(fillPrice);
  const numLot = parseFloat(lot);

  const slippage =
    !isNaN(numFillPrice)
      ? ticket.side === "LONG"
        ? numFillPrice - ticket.entry
        : ticket.entry - numFillPrice
      : 0;

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isNaN(numFillPrice) || numFillPrice <= 0 || isNaN(numLot) || numLot <= 0) {
      setErrorMsg("Mohon isi harga fill dan lot yang valid");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const { data, error } = await apiClient.POST("/api/tickets/{ticket_id}/execute", {
        params: {
          path: { ticket_id: ticket.id },
        },
        body: {
          broker_profile: brokerProfile,
          fill_price: numFillPrice,
          lot: numLot,
          source: "ui",
          notes: notes.trim() || undefined,
        },
      });

      if (error || !data) {
        setErrorMsg("Gagal mencatat eksekusi nyata");
        return;
      }

      setSuccessMsg("Eksekusi berhasil dicatat ke Jurnal Real!");
      if (onExecutionRecorded) {
        onExecutionRecorded();
      }
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch {
      setErrorMsg("Terjadi kesalahan jaringan");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-surface border border-border rounded-xl shadow-2xl max-w-md w-full p-6 text-fg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-fg p-1 rounded-md transition-colors"
          aria-label="Tutup dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-bull/10 border border-bull/20 flex items-center justify-center text-bull">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-fg">Saya Eksekusi Tiket Ini</h3>
            <p className="text-xs text-muted">
              Catat fill nyata ke Jurnal Eksekusi Real ({ticket.symbol} {ticket.side})
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 rounded-lg bg-bear/10 border border-bear/30 flex items-center gap-2 text-xs text-bear">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 rounded-lg bg-bull/10 border border-bull/30 flex items-center gap-2 text-xs text-bull">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleExecute} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Harga Tiket</label>
              <input
                type="text"
                readOnly
                value={ticket.entry}
                className="w-full px-3 py-2 text-sm rounded-lg bg-surface-2 border border-border text-muted font-mono cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Harga Fill Nyata (Broker)
              </label>
              <input
                type="number"
                step="any"
                value={fillPrice}
                onChange={(e) => setFillPrice(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Lot Dijalankan</label>
              <input
                type="number"
                step="any"
                value={lot}
                onChange={(e) => setLot(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Profil Broker</label>
              <select
                value={brokerProfile}
                onChange={(e) => setBrokerProfile(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-fg focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="Exness Standard">Exness Standard</option>
                <option value="IC Markets Raw">IC Markets Raw</option>
                <option value="XM Ultra Low">XM Ultra Low</option>
                <option value="Binance Futures">Binance Futures</option>
              </select>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-surface-2/60 border border-border text-xs flex justify-between items-center">
            <span className="text-muted">Slippage Nyata:</span>
            <span
              className={`font-mono font-bold ${
                slippage === 0 ? "text-muted" : slippage > 0 ? "text-bear" : "text-bull"
              }`}
            >
              {slippage > 0 ? `+${slippage.toFixed(2)}` : slippage.toFixed(2)} poin
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">Catatan (Opsional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Misal: Eksekusi via Exness mobile app saat London session"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-fg placeholder:text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 px-4 rounded-lg border border-border text-xs font-medium text-muted hover:bg-surface-2 transition-colors"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 py-2 px-4 rounded-lg bg-bull text-white text-xs font-bold hover:bg-bull/90 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Mencatat..." : "Konfirmasi Eksekusi"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
