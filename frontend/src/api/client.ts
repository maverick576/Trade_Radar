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
export const api = createClient<paths>({
  baseUrl: getBaseUrl(),
  credentials: "include",
  fetch: (request) => globalThis.fetch(request),
});

api.use(csrfMiddleware);

export const apiClient = api;

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
