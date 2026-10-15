import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { BriefPage } from "./BriefPage";

const mockBriefResponse = {
  id: 1,
  kind: "morning",
  provider: "gemini",
  model: "gemini-2.5-flash",
  created_at: "2026-10-15T06:45:00Z",
  generated_at: "2026-10-15T06:45:00Z",
  is_fallback: false,
  narrative: {
    market_sentiment: "Risk-on",
    ringkasan_umum: "Pasar aset berisiko dan emas menunjukkan penguatan serentak pasca rilis data inflasi moderat.",
    symbols: {
      BTCUSDT: {
        symbol: "BTCUSDT",
        bias: "bullish",
        ringkasan: "BTC menembus resistensi 81000 dengan lonjakan taker volume.",
        skenario: "Melanjutkan penguatan menuju 82500 selama bertengger di atas VWAP.",
        level_kunci: [81000.0, 82500.0, 80200.0],
        fokus_perhatian: "Taker Volume",
      },
      XAUUSD: {
        symbol: "XAUUSD",
        bias: "bullish",
        ringkasan: "Emas bertahan kokoh di atas 2645 didukung pelemahan DXY.",
        skenario: "Pengujian kembali area rekor 2660-2670.",
        level_kunci: [2645.0, 2660.0, 2630.0],
        fokus_perhatian: "DXY & Yields",
      },
    },
  },
  payload: {
    kind: "morning",
    generated_at: "2026-10-15T06:45:00Z",
    symbols: {
      BTCUSDT: {
        symbol: "BTCUSDT",
        bias_h4: "BULL",
        bias_d1: "BULL",
        last_price: 81400.0,
        vwap_yesterday: 80900.0,
        daily_high: 81800.0,
        daily_low: 79800.0,
        score_m15: 62.5,
        verdict_m15: "STRONG_LONG",
      },
      XAUUSD: {
        symbol: "XAUUSD",
        bias_h4: "BULL",
        bias_d1: "BULL",
        last_price: 2652.0,
        vwap_yesterday: 2642.0,
        daily_high: 2658.0,
        daily_low: 2635.0,
        score_m15: 58.0,
        verdict_m15: "STRONG_LONG",
      },
    },
  },
};

describe("BriefPage Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders Market Brief data and multi-asset key levels table", async () => {
    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : "url" in input ? input.url : String(input);
      if (url.includes("/api/briefs/latest")) {
        return Promise.resolve(
          new Response(JSON.stringify(mockBriefResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });

    render(<BriefPage />);

    await waitFor(() => {
      expect(screen.getByText("Market Brief Harian")).toBeInTheDocument();
      expect(screen.getByText("Sentimen: Risk-on")).toBeInTheDocument();
      expect(screen.getByText("Pasar aset berisiko dan emas menunjukkan penguatan serentak pasca rilis data inflasi moderat.")).toBeInTheDocument();
      expect(screen.getByText("Tabel Level Kunci Multi-Aset (Kemarin vs Terkini)")).toBeInTheDocument();
      expect(screen.getByText("BTC menembus resistensi 81000 dengan lonjakan taker volume.")).toBeInTheDocument();
      expect(screen.getByText("Emas bertahan kokoh di atas 2645 didukung pelemahan DXY.")).toBeInTheDocument();
    });
  });

  it("triggers on-demand brief generation when clicking Buat Ulang Brief", async () => {
    let postTriggered = false;

    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : "url" in input ? input.url : String(input);
      const method =
        init?.method ||
        (typeof input === "object" && "method" in input ? (input as Request).method : "GET");

      if (url.includes("/api/briefs")) {
        if (method === "POST") {
          postTriggered = true;
          return Promise.resolve(
            new Response(JSON.stringify(mockBriefResponse), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify(mockBriefResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });

    render(<BriefPage />);

    await waitFor(() => {
      expect(screen.getByText("Buat Ulang Brief")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Buat Ulang Brief"));

    await waitFor(() => {
      expect(postTriggered).toBe(true);
    });
  });
});
