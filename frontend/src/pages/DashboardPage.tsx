import React from "react";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Radio,
  Clock,
  ArrowRight,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { useMarket, type SymbolData } from "../context/MarketContext";

interface DashboardPageProps {
  onSelectSymbol: (symbol: string) => void;
  onNavigateToAnalisa: (symbol: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onSelectSymbol,
  onNavigateToAnalisa,
}) => {
  const { symbols, ticks, wsConnected, goldSourceAlert } = useMarket();

  const handleCardClick = (symbol: string) => {
    onSelectSymbol(symbol);
    onNavigateToAnalisa(symbol);
  };

  return (
    <div className="space-y-6">
      {/* Top Welcome & Feed Status Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface p-6 rounded-2xl border border-border shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold font-mono tracking-tight text-fg">
              Cockpit Ringkasan Pasar
            </h1>
            <span className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-surface-2 border border-border">
              <span
                className={`w-2 h-2 rounded-full ${
                  wsConnected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
                }`}
              />
              {wsConnected ? "Feed Real-time Aktif" : "Feed Terputus"}
            </span>
          </div>
          <p className="text-sm text-muted mt-1">
            Data harga live terhubung langsung ke WebSocket Binance & TradFi Gold.
          </p>
        </div>

        {goldSourceAlert && (
          <div className="px-4 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-500 text-xs flex items-center gap-2">
            <Radio className="w-4 h-4 animate-pulse flex-shrink-0" />
            <span>
              Gold Fallback Aktif: <strong>{goldSourceAlert.active}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Live Market Price Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {symbols.map((sym: SymbolData) => {
          const liveTick = ticks[sym.symbol] || (sym.asset === "gold" ? ticks["XAUUSDT"] : null);
          const displayPrice = liveTick?.price ?? sym.price;
          const isUp = (sym.change_24h ?? 0) >= 0;

          return (
            <div
              key={sym.symbol}
              onClick={() => handleCardClick(sym.symbol)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleCardClick(sym.symbol);
                }
              }}
              tabIndex={0}
              role="button"
              className="group relative bg-surface p-5 rounded-2xl border border-border hover:border-accent/50 transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md flex flex-col justify-between"
            >
              {/* Card Header */}
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold font-mono text-fg group-hover:text-accent transition-colors">
                      {sym.display}
                    </span>
                    <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-surface-2 text-muted border border-border">
                      {sym.asset}
                    </span>
                  </div>

                  {/* 24h Change Pill */}
                  {sym.change_24h !== null && (
                    <span
                      className={`inline-flex items-center gap-0.5 px-2 py-0.5 text-xs font-mono font-semibold rounded-full ${
                        isUp
                          ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                          : "bg-rose-500/10 text-rose-500 border border-rose-500/20"
                      }`}
                    >
                      {isUp ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {isUp ? "+" : ""}
                      {sym.change_24h}%
                    </span>
                  )}
                </div>

                {/* Source Badge */}
                <div className="mt-1 flex items-center gap-1.5 text-[11px] font-mono text-muted">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  <span className="truncate max-w-[180px]">{sym.active_source}</span>
                  {sym.is_fallback && (
                    <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-500 text-[10px] font-bold">
                      FALLBACK
                    </span>
                  )}
                </div>
              </div>

              {/* Live Price Display */}
              <div className="my-4">
                <div className="text-3xl font-extrabold font-mono tracking-tight text-fg">
                  {displayPrice !== null && displayPrice !== undefined ? (
                    displayPrice.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })
                  ) : (
                    <span className="text-muted text-xl animate-pulse">Memuat...</span>
                  )}
                </div>
                <div className="flex items-center justify-between text-xs font-mono text-muted mt-2">
                  <span>H: {sym.high_24h ? sym.high_24h.toFixed(2) : "—"}</span>
                  <span>L: {sym.low_24h ? sym.low_24h.toFixed(2) : "—"}</span>
                </div>
              </div>

              {/* Card Footer: Status & Action */}
              <div className="pt-3 border-t border-border flex items-center justify-between text-xs">
                {sym.asset === "gold" && sym.gold_status ? (
                  <span
                    className={`inline-flex items-center gap-1 font-medium ${
                      sym.gold_status.is_open ? "text-emerald-500" : "text-amber-500"
                    }`}
                  >
                    <Clock className="w-3 h-3" />
                    {sym.gold_status.is_open ? "Sesi Buka" : "Pasar Tutup"}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-muted font-medium">
                    <Activity className="w-3 h-3 text-accent" />
                    24/7 Futures
                  </span>
                )}

                <span className="inline-flex items-center gap-1 text-accent font-semibold group-hover:translate-x-1 transition-transform">
                  Buka Analisa <ArrowRight className="w-3 h-3" />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Feature Highlights Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
        <div className="bg-surface p-5 rounded-2xl border border-border">
          <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center text-accent mb-3">
            <Radio className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-fg text-sm">Pipeline Real-time Tanpa Repaint</h3>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Candle dievaluasi secara deterministik pada candle close M15. Data live diberi label
            khusus dan tidak memicu sinyal prematur.
          </p>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-border">
          <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center text-accent mb-3">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-fg text-sm">Failover Otomatis Pasar Gold</h3>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Rantai sumber cerdas (XAUUSDT → PAXGUSDT → OANDA) secara otomatis beralih saat koneksi
            terganggu tanpa kehilangan kontinuitas chart.
          </p>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-border">
          <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center text-accent mb-3">
            <Zap className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-fg text-sm">TimescaleDB Hypertable & Kompresi</h3>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            Data partisi chunk 7 hari dan kompresi otomatis 30 hari untuk performa kueri
            berkecepatan tinggi dan penyimpanan efisien.
          </p>
        </div>
      </div>
    </div>
  );
};
