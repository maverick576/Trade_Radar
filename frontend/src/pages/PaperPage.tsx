import React, { useState, useEffect, useCallback } from "react";
import { Layers, RefreshCw, AlertCircle, X } from "lucide-react";
import {
  apiClient,
  type PaperAccountResponse,
  type PaperTradeItem,
} from "../api/client";
import { PaperAccountCard } from "../features/paper/PaperAccountCard";
import { PaperTradesTable } from "../features/paper/PaperTradesTable";

export const PaperPage: React.FC = () => {
  const [metrics, setMetrics] = useState<PaperAccountResponse | null>(null);
  const [trades, setTrades] = useState<PaperTradeItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Manual close state
  const [closingTradeId, setClosingTradeId] = useState<number | null>(null);
  const [manualExitPrice, setManualExitPrice] = useState<string>("");
  const [isClosing, setIsClosing] = useState<boolean>(false);
  const [closeError, setCloseError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [accRes, tradesRes] = await Promise.all([
        apiClient.GET("/api/paper/account"),
        apiClient.GET("/api/paper/trades", {
          params: { query: { limit: 150 } },
        }),
      ]);

      if (accRes.data) {
        setMetrics(accRes.data);
      }
      if (tradesRes.data) {
        setTrades(tradesRes.data);
      }
    } catch {
      // Ignore polling errors
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    fetchData().finally(() => setIsLoading(false));
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await fetchData();
    setIsRefreshing(false);
  };

  const handleOpenCloseModal = (tradeId: number, currentPrice: number) => {
    setClosingTradeId(tradeId);
    setManualExitPrice(currentPrice.toString());
    setCloseError(null);
  };

  const handleConfirmClose = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!closingTradeId) return;

    const exitNum = parseFloat(manualExitPrice);
    if (isNaN(exitNum) || exitNum <= 0) {
      setCloseError("Masukkan harga exit yang valid");
      return;
    }

    setIsClosing(true);
    setCloseError(null);

    try {
      const { data, error } = await apiClient.POST("/api/paper/trades/{trade_id}/close", {
        params: {
          path: { trade_id: closingTradeId },
        },
        body: {
          exit_price: exitNum,
          exit_reason: "MANUAL",
        },
      });

      if (error || !data) {
        setCloseError("Gagal menutup posisi paper trade");
        return;
      }

      setClosingTradeId(null);
      await fetchData();
    } catch {
      setCloseError("Terjadi kesalahan jaringan");
    } finally {
      setIsClosing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-fg flex items-center gap-2.5">
            <Layers className="w-7 h-7 text-accent" />
            Posisi & Jurnal Paper Trading
          </h1>
          <p className="text-xs text-muted mt-1">
            Simulasi eksekusi otomatis tanpa modal nyata (modal awal $1.000, risiko 1% per setup, batas rugi harian 3%)
          </p>
        </div>

        <button
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium text-fg hover:bg-surface-2 transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-accent" : "text-muted"}`}
          />
          <span>Segarkan Data</span>
        </button>
      </div>

      {/* KPI Cards */}
      <PaperAccountCard metrics={metrics} isLoading={isLoading} />

      {/* Trades Table */}
      <PaperTradesTable
        trades={trades}
        isLoading={isLoading}
        onCloseTrade={handleOpenCloseModal}
      />

      {/* Manual Close Modal */}
      {closingTradeId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-surface border border-border rounded-xl shadow-2xl max-w-sm w-full p-6 text-fg relative">
            <button
              onClick={() => setClosingTradeId(null)}
              className="absolute top-4 right-4 text-muted hover:text-fg p-1 rounded-md transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-fg mb-1">Tutup Posisi Paper Manual</h3>
            <p className="text-xs text-muted mb-4">
              Konfirmasi penutupan posisi #{closingTradeId} pada harga pasar saat ini.
            </p>

            {closeError && (
              <div className="mb-4 p-2.5 rounded bg-bear/10 border border-bear/30 text-xs text-bear flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{closeError}</span>
              </div>
            )}

            <form onSubmit={handleConfirmClose} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Harga Exit</label>
                <input
                  type="number"
                  step="any"
                  value={manualExitPrice}
                  onChange={(e) => setManualExitPrice(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-surface-2 border border-border text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent"
                  required
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setClosingTradeId(null)}
                  className="flex-1 py-2 px-3 rounded-lg border border-border text-xs font-medium text-muted hover:bg-surface-2 transition-colors"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={isClosing}
                  className="flex-1 py-2 px-3 rounded-lg bg-accent text-white text-xs font-bold hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {isClosing ? "Menutup..." : "Konfirmasi Tutup"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
