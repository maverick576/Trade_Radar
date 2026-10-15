import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  AlertTriangle,
  Clock,
  RefreshCw,
  Activity,
  Layers,
} from "lucide-react";
import {
  TradingViewChart,
  type ChartCandle,
  type ChartOverlays,
  type ChartPanes,
} from "../components/chart/TradingViewChart";
import { useMarket } from "../context/MarketContext";
import { apiClient, type CandleItem } from "../api/client";

interface IndicatorResultItem {
  key: string;
  category: string;
  state: "BULL" | "BEAR" | "NEUTRAL" | "NA";
  strength: number;
  values: Record<string, number>;
  reason: string;
  live_only?: boolean;
}

interface IndicatorsApiResponse {
  symbol: string;
  tf: string;
  overlays: ChartOverlays;
  panes: ChartPanes;
  latest_indicators: IndicatorResultItem[];
  calc_time_ms: number;
}

interface AnalisaPageProps {
  symbol: string;
  onSelectSymbol: (symbol: string) => void;
}

const INDICATOR_LABELS: Record<string, { name: string; cat: string }> = {
  vwap: { name: "VWAP", cat: "Order Flow" },
  ema_ribbon: { name: "EMA Ribbon", cat: "Trend" },
  supertrend: { name: "Supertrend", cat: "Trend" },
  rsi_div: { name: "RSI Divergence", cat: "Momentum" },
  bollinger: { name: "Bollinger Bands", cat: "Momentum" },
  cvd_obv: { name: "CVD / OBV", cat: "Order Flow" },
  funding_oi: { name: "Funding & OI", cat: "Derivatives" },
  orderbook: { name: "Order Book", cat: "Microstructure" },
  lightgbm: { name: "LightGBM ML", cat: "Machine Learning" },
  sentiment: { name: "Sentimen", cat: "Sentiment" },
};

export const AnalisaPage: React.FC<AnalisaPageProps> = ({
  symbol,
  onSelectSymbol,
}) => {
  const { ticks, latestCandle, symbols, goldSourceAlert, wsConnected, subscribe } = useMarket();
  const [selectedTf, setSelectedTf] = useState<string>("M15");
  const [candles, setCandles] = useState<ChartCandle[]>([]);
  const [indicatorsData, setIndicatorsData] = useState<IndicatorsApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [lastTickPrice, setLastTickPrice] = useState<number | null>(null);
  const [priceFlash, setPriceFlash] = useState<"up" | "down" | null>(null);

  // Overlay and Pane Toggles
  const [activeOverlays, setActiveOverlays] = useState({
    vwap: true,
    ema_ribbon: false,
    supertrend: true,
    bollinger: false,
  });

  const [activePanes, setActivePanes] = useState({
    rsi: true,
    cvd: false,
  });

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

  // Fetch overlays, sub-panes and indicator verdicts
  const fetchIndicators = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/indicators", {
        params: {
          query: {
            symbol: querySymbol,
            tf: selectedTf,
            limit: 300,
          },
        },
      });

      if (res.data) {
        setIndicatorsData(res.data as IndicatorsApiResponse);
      }
    } catch (err) {
      console.error("Gagal memuat indikator:", err);
    }
  }, [querySymbol, selectedTf]);

  useEffect(() => {
    fetchCandles();
    fetchIndicators();
    subscribe([querySymbol, symbol], [selectedTf]);
  }, [fetchCandles, fetchIndicators, querySymbol, symbol, selectedTf, subscribe]);

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

  const handleToggleOverlay = (key: "vwap" | "ema_ribbon" | "supertrend" | "bollinger") => {
    setActiveOverlays((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleTogglePane = (key: "rsi" | "cvd") => {
    setActivePanes((prev) => ({ ...prev, [key]: !prev[key] }));
  };

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-4 rounded-xl border border-border shadow-sm">
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
              10 Indikator Konfluensi & Analisis Multi-Timeframe
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
                      ? "bg-accent text-accent-fg shadow-sm font-bold"
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
            onClick={() => {
              fetchCandles();
              fetchIndicators();
            }}
            disabled={isLoading}
            className="p-2 rounded-lg bg-surface-2 border border-border text-muted hover:text-fg hover:bg-surface transition-colors"
            title="Muat ulang chart & indikator"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Chart Canvas with Overlays & Panes */}
      <div className="w-full">
        {isLoading && candles.length === 0 ? (
          <div className="w-full h-[480px] bg-surface rounded-xl border border-border flex flex-col items-center justify-center text-muted">
            <RefreshCw className="w-8 h-8 animate-spin text-accent mb-2" />
            <span className="text-sm font-semibold">Memuat data market & indikator...</span>
          </div>
        ) : (
          <TradingViewChart
            candles={candles}
            liveCandle={liveBar || null}
            symbol={currentSymbolMeta?.display || symbol}
            tf={selectedTf}
            overlays={indicatorsData?.overlays}
            panes={indicatorsData?.panes}
            activeOverlays={activeOverlays}
            activePanes={activePanes}
            onToggleOverlay={handleToggleOverlay}
            onTogglePane={handleTogglePane}
          />
        )}
      </div>

      {/* 10 Indicators Real-time Confluence Section */}
      {indicatorsData?.latest_indicators && indicatorsData.latest_indicators.length > 0 && (
        <div className="bg-surface rounded-xl border border-border p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-bold text-fg tracking-wide">
                Status 10 Indikator (Strategi Konfluensi)
              </h3>
              <span className="text-xs text-muted font-mono">
                {selectedTf} Candle Close
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-muted">
              <span>Durasi hitung:</span>
              <strong className="text-accent">{indicatorsData.calc_time_ms} ms</strong>
              <span className="text-[10px] text-emerald-400 font-semibold">(target &lt; 300 ms)</span>
            </div>
          </div>

          {/* Grid of 10 Indicators */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
            {indicatorsData.latest_indicators.map((ind) => {
              const meta = INDICATOR_LABELS[ind.key] || { name: ind.key, cat: ind.category };
              const isBull = ind.state === "BULL";
              const isBear = ind.state === "BEAR";
              const isNeutral = ind.state === "NEUTRAL";

              const badgeColor = isBull
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-500"
                : isBear
                ? "bg-rose-500/15 border-rose-500/30 text-rose-500"
                : isNeutral
                ? "bg-amber-500/10 border-amber-500/20 text-amber-500"
                : "bg-surface-2 border-border text-muted";

              const strengthPct = Math.round(ind.strength * 100);

              return (
                <div
                  key={ind.key}
                  className="p-2.5 rounded-lg bg-surface-2/40 border border-border hover:border-accent/40 transition-colors flex flex-col justify-between"
                  title={ind.reason}
                >
                  <div className="flex items-start justify-between gap-1 mb-1.5">
                    <div>
                      <div className="font-semibold text-xs text-fg">{meta.name}</div>
                      <div className="text-[10px] text-muted">{meta.cat}</div>
                    </div>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono border ${badgeColor}`}
                    >
                      {ind.state}
                    </span>
                  </div>

                  {/* Strength Bar */}
                  {ind.state !== "NA" && (
                    <div className="space-y-1 mt-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-muted">
                        <span>Kekuatan</span>
                        <strong className="text-fg">{strengthPct}%</strong>
                      </div>
                      <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            isBull
                              ? "bg-emerald-500"
                              : isBear
                              ? "bg-rose-500"
                              : "bg-amber-500"
                          }`}
                          style={{ width: `${Math.max(strengthPct, 6)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Indonesian reason tooltip hint */}
                  <p className="text-[11px] text-muted line-clamp-2 mt-2 leading-relaxed">
                    {ind.reason}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer Status Bar */}
      <div className="flex flex-wrap items-center justify-between text-xs text-muted px-2 py-1">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span>WebSocket {wsConnected ? "Tersambung (Real-time)" : "Terputus"}</span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 text-muted/80">
            <Activity className="w-3.5 h-3.5 text-accent" />
            <span>Kalkulasi 10 Indikator Inkremental Aktif</span>
          </div>
        </div>

        {isGold && currentSymbolMeta?.gold_status && (
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-accent" />
            <span>
              Sesi Pasar Gold:{" "}
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
