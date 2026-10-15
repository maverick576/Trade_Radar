import React, { useState } from "react";
import { CheckCircle2, X, AlertCircle } from "lucide-react";
import { apiClient, type TicketItem } from "../../api/client";

interface CloseExecutionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  ticket: TicketItem;
  onClosed?: () => void;
}

export const CloseExecutionDialog: React.FC<CloseExecutionDialogProps> = ({
  isOpen,
  onClose,
  ticket,
  onClosed,
}) => {
  const [exitPrice, setExitPrice] = useState<string>(ticket.tp1.toString());
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const numExit = parseFloat(exitPrice);

  const handleClose = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isNaN(numExit) || numExit <= 0) {
      setErrorMsg("Masukkan harga exit yang valid");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const { data, error } = await apiClient.POST("/api/tickets/{ticket_id}/close", {
        params: {
          path: { ticket_id: ticket.id },
        },
        body: {
          exit_price: numExit,
          notes: notes.trim() || undefined,
        },
      });

      if (error || !data) {
        setErrorMsg("Gagal menutup posisi tiket");
        return;
      }

      if (onClosed) {
        onClosed();
      }
      onClose();
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
          <div className="w-10 h-10 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center text-accent">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-fg">Tutup Posisi Eksekusi Real</h3>
            <p className="text-xs text-muted">
              Catat harga penutupan untuk menghitung PnL final ({ticket.symbol} {ticket.side})
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 rounded-lg bg-bear/10 border border-bear/30 flex items-center gap-2 text-xs text-bear">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleClose} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Harga Exit Nyata</label>
            <input
              type="number"
              step="any"
              value={exitPrice}
              onChange={(e) => setExitPrice(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">Catatan Exit (Opsional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Contoh: Exit manual karena rilis berita High USD"
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
              className="flex-1 py-2 px-4 rounded-lg bg-accent text-white text-xs font-bold hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Menyimpan..." : "Tutup Posisi"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
