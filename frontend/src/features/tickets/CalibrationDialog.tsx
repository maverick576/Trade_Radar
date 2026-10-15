import React, { useState } from "react";
import { Sliders, X, Check, AlertCircle } from "lucide-react";
import { apiClient } from "../../api/client";

interface CalibrationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  symbol: string;
  sourcePrice: number;
  currentOffset?: number | null;
  onCalibrationSaved?: (offset: number) => void;
}

export const CalibrationDialog: React.FC<CalibrationDialogProps> = ({
  isOpen,
  onClose,
  symbol,
  sourcePrice,
  currentOffset,
  onCalibrationSaved,
}) => {
  const [brokerPrice, setBrokerPrice] = useState<string>(
    currentOffset ? (sourcePrice + currentOffset).toFixed(2) : sourcePrice.toFixed(2)
  );
  const [brokerProfile, setBrokerProfile] = useState<string>("Exness Standard");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const numBrokerPrice = parseFloat(brokerPrice);
  const calculatedOffset =
    !isNaN(numBrokerPrice) && numBrokerPrice > 0 ? numBrokerPrice - sourcePrice : 0;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isNaN(numBrokerPrice) || numBrokerPrice <= 0) {
      setErrorMsg("Masukkan harga broker yang valid");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const { data, error } = await apiClient.POST("/api/calibrations", {
        body: {
          symbol,
          broker_profile: brokerProfile,
          broker_price: numBrokerPrice,
        },
      });

      if (error || !data) {
        setErrorMsg("Gagal menyimpan kalibrasi broker");
        return;
      }

      setSuccessMsg(`Offset ${data.offset >= 0 ? "+" : ""}${data.offset.toFixed(2)} berhasil disimpan (aktif 30 menit)`);
      if (onCalibrationSaved) {
        onCalibrationSaved(data.offset);
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
          <div className="w-10 h-10 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center text-accent">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-fg">Kalibrasi Harga Broker</h3>
            <p className="text-xs text-muted">Sesuaikan offset harga sumber ke terminal broker Anda</p>
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
            <Check className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Simbol</label>
            <input
              type="text"
              readOnly
              value={symbol}
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface-2 border border-border text-fg font-mono cursor-not-allowed"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">Harga Sumber Saat Ini</label>
            <input
              type="text"
              readOnly
              value={sourcePrice.toFixed(2)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface-2 border border-border text-muted font-mono cursor-not-allowed"
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
              <option value="Binance Futures">Binance Futures (No Offset)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Harga di Broker Anda Sekarang
            </label>
            <input
              type="number"
              step="any"
              value={brokerPrice}
              onChange={(e) => setBrokerPrice(e.target.value)}
              placeholder="Contoh: 2652.3"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface-2 border border-border text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent"
              required
            />
          </div>

          <div className="p-3 rounded-lg bg-surface-2/60 border border-border text-xs flex justify-between items-center">
            <span className="text-muted">Offset Terhitung:</span>
            <span className={`font-mono font-bold ${calculatedOffset >= 0 ? "text-bull" : "text-bear"}`}>
              {calculatedOffset >= 0 ? `+${calculatedOffset.toFixed(2)}` : calculatedOffset.toFixed(2)} poin
            </span>
          </div>

          <p className="text-[11px] text-muted leading-relaxed">
            * Offset berlaku selama 30 menit. Seluruh level Entry, SL, dan TP pada tiket akan disesuaikan secara otomatis.
          </p>

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
              className="flex-1 py-2 px-4 rounded-lg bg-accent text-white text-xs font-medium hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Menyimpan..." : "Terapkan Offset"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
