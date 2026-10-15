/**
 * Strongly-typed API client generated from OpenAPI schema.
 */

import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./generated/schema";

/**
 * Retrieve CSRF token from document cookies.
 */
export function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)traderadar_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

// Middleware to automatically attach CSRF header to state-changing requests
const csrfMiddleware: Middleware = {
  async onRequest({ request }) {
    const method = request.method.toUpperCase();
    if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
      const token = getCsrfToken();
      if (token) {
        request.headers.set("X-CSRF-Token", token);
      }
    }
    return request;
  },
};

const getBaseUrl = (): string => {
  if (typeof window !== "undefined" && window.location?.origin && window.location.origin !== "null") {
    return window.location.origin;
  }
  return "http://localhost:8080";
};

/**
 * Singleton API client for making backend REST calls.
 */
export const apiClient = createClient<paths>({
  baseUrl: getBaseUrl(),
  credentials: "include",
  fetch: (request) => globalThis.fetch(request),
});

apiClient.use(csrfMiddleware);

export type UserProfile =
  paths["/api/auth/me"]["get"]["responses"][200]["content"]["application/json"];
export type LoginPayload =
  paths["/api/auth/login"]["post"]["requestBody"]["content"]["application/json"];
export type FullHealthResponse =
  paths["/api/health/full"]["get"]["responses"][200]["content"]["application/json"];
export type SymbolsResponse =
  paths["/api/symbols"]["get"]["responses"][200]["content"]["application/json"];
export type CandleItem =
  paths["/api/candles"]["get"]["responses"][200]["content"]["application/json"][number];
export type AnalysisResponse =
  paths["/api/analysis/{symbol}"]["get"]["responses"][200]["content"]["application/json"];
export type ScoreHistoryResponse =
  paths["/api/analysis/{symbol}/history"]["get"]["responses"][200]["content"]["application/json"];
export type SignalsResponse =
  paths["/api/signals"]["get"]["responses"][200]["content"]["application/json"];
export type SignalItem = SignalsResponse["signals"][number];
export type TicketItem =
  paths["/api/tickets"]["get"]["responses"][200]["content"]["application/json"][number];
export type ExecuteTicketPayload =
  paths["/api/tickets/{ticket_id}/execute"]["post"]["requestBody"]["content"]["application/json"];
export type CloseTicketPayload =
  paths["/api/tickets/{ticket_id}/close"]["post"]["requestBody"]["content"]["application/json"];
export type CalibrationPayload =
  paths["/api/calibrations"]["post"]["requestBody"]["content"]["application/json"];
export type CalibrationResponse =
  paths["/api/calibrations"]["post"]["responses"][200]["content"]["application/json"];
export type PaperTradeItem =
  paths["/api/paper/trades"]["get"]["responses"][200]["content"]["application/json"][number];
export type PaperAccountResponse =
  paths["/api/paper/account"]["get"]["responses"][200]["content"]["application/json"];
export type ClosePaperTradePayload =
  paths["/api/paper/trades/{trade_id}/close"]["post"]["requestBody"]["content"]["application/json"];
export type AICommentResponse =
  paths["/api/analysis/{symbol}/ai"]["get"]["responses"][200]["content"]["application/json"];
export type AIComment = AICommentResponse["comment"];
export type MarketBriefResponse =
  paths["/api/briefs/latest"]["get"]["responses"][200]["content"]["application/json"];
export type AIQuotaResponse =
  paths["/api/ai/quota"]["get"]["responses"][200]["content"]["application/json"];
export type JournalResponse =
  paths["/api/stats"]["get"]["responses"][200]["content"]["application/json"];
export type TradeRecordItem = NonNullable<JournalResponse["trades"]>[number];
export type JournalKPIs = JournalResponse["kpis"];
export type EquityPoint = NonNullable<JournalResponse["equity_curve"]>[number];
export type HeatmapCell = NonNullable<JournalResponse["heatmap"]>[number];
export type BreakdownItem = NonNullable<NonNullable<JournalResponse["breakdowns"]>[string]>[number];
export type IndicatorAccuracyItem = NonNullable<JournalResponse["indicator_accuracy"]>[number];
export type MacroFilterImpactItem = NonNullable<JournalResponse["macro_filter_impact"]>[number];
export type SlippageStats = JournalResponse["slippage_metrics"];
export type TradeAnalysisSnapshotResponse =
  paths["/api/stats/trades/{trade_id}/snapshot"]["get"]["responses"][200]["content"]["application/json"];

export type JournalBookType = "paper" | "real" | "compare";

export const getJournalStats = async (params: {
  book?: string;
  range_str?: string;
  symbol?: string;
  strategy?: string;
  date_from?: string;
  date_to?: string;
}): Promise<JournalResponse> => {
  const res = await apiClient.GET("/api/stats", {
    params: {
      query: {
        book: params.book as "paper" | "real" | "compare" | undefined,
        range: params.range_str,
        symbol: params.symbol,
        strategy: params.strategy,
        from_dt: params.date_from,
        to_dt: params.date_to,
      },
    },
  });
  if (res.error) throw new Error(String(res.error));
  return res.data as JournalResponse;
};

export const getTradeSnapshot = async (
  tradeId: string
): Promise<TradeAnalysisSnapshotResponse> => {
  const res = await apiClient.GET("/api/stats/trades/{trade_id}/snapshot", {
    params: {
      path: { trade_id: Number(tradeId) },
    },
  });
  if (res.error) throw new Error(String(res.error));
  return res.data as TradeAnalysisSnapshotResponse;
};

export const exportJournalCsv = async (params: {
  book?: string;
  range_str?: string;
  symbol?: string;
  strategy?: string;
  date_from?: string;
  date_to?: string;
}): Promise<void> => {
  const searchParams = new URLSearchParams();
  if (params.book) searchParams.set("book", params.book);
  if (params.range_str) searchParams.set("range", params.range_str);
  if (params.symbol) searchParams.set("symbol", params.symbol);
  if (params.strategy) searchParams.set("strategy", params.strategy);
  if (params.date_from) searchParams.set("from_dt", params.date_from);
  if (params.date_to) searchParams.set("to_dt", params.date_to);

  const url = `${getBaseUrl()}/api/stats/export.csv?${searchParams.toString()}`;
  const res = await globalThis.fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`Gagal ekspor CSV: ${res.statusText}`);
  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = `traderadar_journal_${params.book || "paper"}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(downloadUrl);
};

export const api = Object.assign(apiClient, {
  getJournalStats,
  getTradeSnapshot,
  exportJournalCsv,
});


