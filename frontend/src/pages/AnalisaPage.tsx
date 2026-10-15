import React, { useEffect, useState, useCallback, useRef } from "react";
import { AlertTriangle, Clock, RefreshCw } from "lucide-react";
import { TradingViewChart, type ChartCandle } from "../components/chart/TradingViewChart";
import { useMarket } from "../context/MarketContext";
import { apiClient, type CandleItem } from "../api/client";

interface AnalisaPageProps {
  symbol: string;
  onSelectSymbol: (symbol: string) => void;
}

export const AnalisaPage: React.FC<AnalisaPageProps> = ({
  symbol,
  onSelectSymbol,
}) => {
  const { ticks, latestCandle, symbols, goldSourceAlert, wsConnected, subscribe } = useMarket();
  const [selectedTf, setSelectedTf] = useState<string>("M15");
  const [candles, setCandles] = useState<ChartCandle[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [lastTickPrice, setLastTickPrice] = useState<number | null>(null);
  const [priceFlash, setPriceFlash] = useState<"up" | "down" | null>(null);

  const prevPriceRef = useRef<number | null>(null);

  // Normalize symbol query
  const querySymbol = symbol === "XAUUSDT" ? "XAUUSD" : symbol;
  const currentSymbolMeta = symbols.find(
    (s) => s.symbol === querySymbol || s.symbol === symbol
  );

  const isGold = querySymbol === "XAUUSD" || symbol === "XAUUSDT";
  const isFallback = Boolean(
    isGold && (currentSymbolMeta?.is_fallback || goldSourceAlert?.active.includes("PAXG"))
  );

  const timeframes = ["M15", "H1", "H4", "D1"];

  // Fetch initial candles
  const fetchCandles = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.GET("/api/candles", {
        params: {
          query: {
            symbol: querySymbol,
            tf: selectedTf,
            limit: 300,
          },
        },
      });

      if (res.data) {
        const rawList = res.data as CandleItem[];
        const formatted: ChartCandle[] = rawList.map((c) => ({
          open_time: c.open_time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
          is_closed: c.is_closed,
        }));
        setCandles(formatted);
      }
    } catch (err) {
      console.error("Gagal memuat candles:", err);
    } finally {
      setIsLoading(false);
    }
  }, [querySymbol, selectedTf]);

  useEffect(() => {
    fetchCandles();
    subscribe([querySymbol, symbol], [selectedTf]);
  }, [fetchCandles, querySymbol, symbol, selectedTf, subscribe]);

  // Tick flash detection
  const liveTick = ticks[querySymbol] || ticks[symbol];
  useEffect(() => {
    if (liveTick?.price) {
      const curPrice = liveTick.price;
      if (prevPriceRef.current !== null && prevPriceRef.current !== curPrice) {
        setPriceFlash(curPrice > prevPriceRef.current ? "up" : "down");
        const timer = setTimeout(() => setPriceFlash(null), 800);
        prevPriceRef.current = curPrice;
        setLastTickPrice(curPrice);
        return () => clearTimeout(timer);
      }
      prevPriceRef.current = curPrice;
      setLastTickPrice(curPrice);
    }
  }, [liveTick]);

  // Merge live running bar from websocket
  const liveBarKey = `${querySymbol}:${selectedTf}`;
  const liveBar = latestCandle[liveBarKey];

  return (
    <div className="space-y-4">
      {/* Fallback Banner for Gold */}
      {isFallback && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-500 flex items-start gap-3 shadow-sm animate-pulse"
        >
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5 text-amber-500" />
          <div className="text-sm">
            <h4 className="font-semibold text-amber-500">
              Perhatian Sumber Data: Mode Cadangan PAXGUSDT Aktif
            </h4>
            <p className="mt-0.5 text-xs text-amber-500/90 leading-relaxed">
              Koneksi ke data Binance Futures XAUUSDT terputus/terkendala (
              {goldSourceAlert?.reason || "Timeout > 120s"}). Sistem secara otomatis beralih
              menggunakan Binance Spot PAXGUSDT demi menjaga kontinuitas analisis.
            </p>
          </div>
        </div>
      )}

      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-4 rounded-xl border border-border">
        {/* Left: Symbol & Live Price */}
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold font-mono tracking-tight text-fg">
                {currentSymbolMeta?.display || symbol}
              </h2>
              <span className="px-2 py-0.5 text-[11px] font-semibold uppercase rounded-full bg-surface-2 border border-border text-muted">
                {currentSymbolMeta?.asset || (isGold ? "Gold" : "Crypto")}
              </span>
              <span className="px-2 py-0.5 text-[11px] font-mono rounded bg-accent/10 border border-accent/20 text-accent font-medium">
                {currentSymbolMeta?.active_source || (isFallback ? "binance_spot:PAXGUSDT" : "binance_futures")}
              </span>
            </div>
            <p className="text-xs text-muted mt-0.5">
              Multi-timeframe confluence and real-time market data
            </p>
          </div>

          {/* Live Price Display */}
          <div className="pl-4 border-l border-border">
            <div className="text-xs text-muted font-medium">Harga Live</div>
            <div
              className={`text-2xl font-bold font-mono transition-colors duration-300 ${
                priceFlash === "up"
                  ? "text-emerald-500 scale-105"
                  : priceFlash === "down"
                  ? "text-rose-500 scale-105"
                  : "text-fg"
              }`}
            >
              {lastTickPrice !== null
                ? lastTickPrice.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })
                : "—"}
            </div>
          </div>
        </div>

        {/* Right: Symbol Quick-Select & Timeframe Selector & Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-surface-2 p-1 rounded-lg border border-border">
            {symbols.map((s) => {
              const active = s.symbol === querySymbol || s.symbol === symbol;
              return (
                <button
                  key={s.symbol}
                  type="button"
                  onClick={() => onSelectSymbol(s.symbol)}
                  className={`px-2.5 py-1 text-xs font-mono font-semibold rounded transition-colors ${
                    active
                      ? "bg-surface text-accent shadow-sm font-bold"
                      : "text-muted hover:text-fg hover:bg-surface/50"
                  }`}
                >
                  {s.display}
                </button>
              );
            })}
          </div>

          <div className="flex items-center bg-surface-2 p-1 rounded-lg border border-border">
            {timeframes.map((tf) => {
              const active = selectedTf === tf;
              return (
                <button
                  key={tf}
                  type="button"
                  onClick={() => setSelectedTf(tf)}
                  className={`px-3 py-1 text-xs font-mono font-semibold rounded transition-colors ${
                    active
                      ? "bg-accent text-accent-fg shadow-sm"
                      : "text-muted hover:text-fg hover:bg-surface"
                  }`}
                >
                  {tf}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => fetchCandles()}
            disabled={isLoading}
            className="p-2 rounded-lg bg-surface-2 border border-border text-muted hover:text-fg hover:bg-surface transition-colors"
            title="Muat ulang data chart"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Chart Section */}
      <div className="w-full">
        {isLoading && candles.length === 0 ? (
          <div className="w-full h-[480px] bg-surface rounded-xl border border-border flex flex-col items-center justify-center text-muted">
            <RefreshCw className="w-8 h-8 animate-spin text-accent mb-2" />
            <span className="text-sm font-semibold">Memuat data candle Binance...</span>
          </div>
        ) : (
          <TradingViewChart
            candles={candles}
            liveCandle={liveBar || null}
            symbol={currentSymbolMeta?.display || symbol}
            tf={selectedTf}
          />
        )}
      </div>

      {/* Status Bar */}
      <div className="flex flex-wrap items-center justify-between text-xs text-muted px-2 py-1">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              wsConnected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
            }`}
          />
          <span>WebSocket {wsConnected ? "Tersambung (Real-time)" : "Terputus"}</span>
        </div>
        {isGold && currentSymbolMeta?.gold_status && (
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-accent" />
            <span>
              Sesi Pasar:{" "}
              <strong className="text-fg">
                {currentSymbolMeta.gold_status.is_open ? "BUKA" : "TUTUP"}
              </strong>
              {currentSymbolMeta.gold_status.reason && (
                <span className="ml-1 text-amber-500/90">
                  ({currentSymbolMeta.gold_status.reason})
                </span>
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
