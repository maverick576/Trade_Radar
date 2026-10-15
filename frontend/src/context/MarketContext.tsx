import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from "react";
import { apiClient } from "../api/client";

export interface SymbolData {
  symbol: string;
  display: string;
  asset: "crypto" | "gold";
  active_source: string;
  is_fallback: boolean;
  price: number | null;
  change_24h: number | null;
  high_24h: number | null;
  low_24h: number | null;
  capabilities: string[];
  gold_status: {
    is_open: boolean;
    is_rollover: boolean;
    is_dst: boolean;
    reason: string | null;
    wib_time: string;
  } | null;
}

export interface CandleData {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_closed: boolean;
}

interface MarketContextType {
  symbols: SymbolData[];
  ticks: Record<string, { price: number; ts: string }>;
  latestCandle: Record<string, CandleData>; // key: `${symbol}:${tf}`
  goldSourceAlert: { active: string; previous?: string; reason?: string } | null;
  wsConnected: boolean;
  refreshSymbols: () => Promise<void>;
  subscribe: (symbols: string[], tfs: string[]) => void;
}

const MarketContext = createContext<MarketContextType | undefined>(undefined);

export const MarketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [symbols, setSymbols] = useState<SymbolData[]>([]);
  const [ticks, setTicks] = useState<Record<string, { price: number; ts: string }>>({});
  const [latestCandle, setLatestCandle] = useState<Record<string, CandleData>>({});
  const [goldSourceAlert, setGoldSourceAlert] = useState<{
    active: string;
    previous?: string;
    reason?: string;
  } | null>(null);
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSymbols = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/symbols");
      if (res.data?.symbols) {
        const list = res.data.symbols as SymbolData[];
        setSymbols(list);
        // If gold is fallback, initialize alert
        const gold = list.find((s) => s.asset === "gold");
        if (gold && gold.is_fallback) {
          setGoldSourceAlert({
            active: gold.active_source,
            reason: "Menggunakan sumber cadangan PAXGUSDT",
          });
        }
      }
    } catch (e) {
      console.warn("Gagal memuat symbols:", e);
    }
  }, []);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Use current origin ws protocol
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    // If running in dev mode (Vite on :5173), connect to backend port 8080 or current host
    const host = window.location.port === "5173" ? "localhost:8080" : window.location.host;
    const wsUrl = `${proto}//${host}/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      // Subscribe to all watchlist symbols
      ws.send(
        JSON.stringify({
          type: "subscribe",
          symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSD", "XAUUSDT"],
          tfs: ["M15", "H1", "H4", "D1"],
        })
      );
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "tick") {
          const sym = msg.data.symbol;
          const price = msg.data.price;
          const ts = msg.data.ts;
          setTicks((prev) => ({
            ...prev,
            [sym]: { price, ts },
            // Also mirror XAUUSD and XAUUSDT for consistent lookup
            ...(sym === "XAUUSD" ? { XAUUSDT: { price, ts } } : {}),
            ...(sym === "XAUUSDT" ? { XAUUSD: { price, ts } } : {}),
          }));
        } else if (msg.type === "candle" || msg.type === "live_bar") {
          const sym = msg.data.symbol;
          const tf = msg.data.tf;
          const bar = msg.data.bar || msg.data;
          const key = `${sym}:${tf}`;
          setLatestCandle((prev) => ({
            ...prev,
            [key]: {
              open_time: bar.open_time,
              open: bar.open,
              high: bar.high,
              low: bar.low,
              close: bar.close,
              volume: bar.volume,
              is_closed: Boolean(bar.is_closed),
            },
          }));
        } else if (msg.type === "gold_source_changed") {
          setGoldSourceAlert({
            active: msg.data.active,
            previous: msg.data.previous,
            reason: msg.data.reason,
          });
          // Refresh symbols to update badges
          fetchSymbols();
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      wsRef.current = null;
      // Reconnect after 3s
      if (!reconnectTimeoutRef.current) {
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connectWs();
        }, 3000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [fetchSymbols]);

  const subscribe = useCallback((subSymbols: string[], subTfs: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "subscribe",
          symbols: subSymbols,
          tfs: subTfs,
        })
      );
    }
  }, []);

  // Ping interval to keep connection alive
  useEffect(() => {
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 20000);

    return () => clearInterval(pingInterval);
  }, []);

  useEffect(() => {
    fetchSymbols();
    connectWs();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [fetchSymbols, connectWs]);

  return (
    <MarketContext.Provider
      value={{
        symbols,
        ticks,
        latestCandle,
        goldSourceAlert,
        wsConnected,
        refreshSymbols: fetchSymbols,
        subscribe,
      }}
    >
      {children}
    </MarketContext.Provider>
  );
};

export const useMarket = (): MarketContextType => {
  const context = useContext(MarketContext);
  if (!context) {
    throw new Error("useMarket must be used within a MarketProvider");
  }
  return context;
};
