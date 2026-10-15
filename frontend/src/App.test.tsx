import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import App from "./App";

describe("TradeRadar App & Shell", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders LoginPage when user is not authenticated", async () => {
    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : "url" in input ? input.url : String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              error: { code: "UNAUTHORIZED", message: "Autentikasi diperlukan." },
            }),
            { status: 401, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("TradeRadar")).toBeInTheDocument();
      expect(screen.getByText("Masuk ke Akun")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("admin@example.com")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("••••••••••••")).toBeInTheDocument();
    });
  });

  it("renders Shell when user is authenticated", async () => {
    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : "url" in input ? input.url : String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: 1,
              email: "admin@example.com",
              totp_enabled: false,
              created_at: "2026-10-15T00:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      if (url.includes("/api/health/full")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              status: "healthy",
              version: "0.1.0-dev",
              timestamp: "2026-10-15T00:00:00Z",
              infrastructure: {
                database: "healthy",
                redis: "healthy",
              },
              services: {
                api: { service: "api", status: "healthy" },
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      if (url.includes("/api/symbols")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              symbols: [
                {
                  symbol: "BTCUSDT",
                  display: "BTCUSD",
                  asset: "crypto",
                  active_source: "binance_futures:BTCUSDT",
                  is_fallback: false,
                  price: 81250.0,
                  change_24h: 2.5,
                  high_24h: 82000.0,
                  low_24h: 80000.0,
                  capabilities: ["vwap", "ema_ribbon"],
                  gold_status: null,
                },
                {
                  symbol: "XAUUSD",
                  display: "XAUUSD",
                  asset: "gold",
                  active_source: "binance_futures:XAUUSDT",
                  is_fallback: false,
                  price: 2650.5,
                  change_24h: 0.8,
                  high_24h: 2660.0,
                  low_24h: 2640.0,
                  capabilities: ["vwap", "ema_ribbon"],
                  gold_status: {
                    is_open: true,
                    is_rollover: false,
                    is_dst: false,
                    reason: null,
                    wib_time: "2026-10-15T12:00:00+07:00",
                  },
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      expect(screen.getByText("Cockpit Ringkasan Pasar")).toBeInTheDocument();
    });
  });
});
