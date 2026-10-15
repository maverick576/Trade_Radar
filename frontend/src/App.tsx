import React, { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Layers,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  Zap,
} from "lucide-react";

interface ServiceStatus {
  service: string;
  status: string;
  version?: string;
  ts?: string;
  uptime_seconds?: number;
}

interface FullHealthResponse {
  status: string;
  version: string;
  timestamp: string;
  infrastructure: {
    database: string;
    redis: string;
  };
  services: Record<string, ServiceStatus | null>;
}

export default function App() {
  const [data, setData] = useState<FullHealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastChecked, setLastChecked] = useState<string>("");

  const fetchHealth = async () => {
    const start = performance.now();
    try {
      const res = await fetch("/api/health/full");
      const elapsed = Math.round(performance.now() - start);
      setLatencyMs(elapsed);

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const json: FullHealthResponse = await res.json();
      setData(json);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal terhubung ke API backend");
    } finally {
      setLoading(false);
      setLastChecked(new Date().toLocaleTimeString("id-ID", { timeZone: "Asia/Jakarta" }) + " WIB");
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 3000);
    return () => clearInterval(interval);
  }, []);

  const serviceIcons: Record<string, React.ReactNode> = {
    api: <Zap className="w-5 h-5 text-accent" />,
    ingestor: <Radio className="w-5 h-5 text-bull" />,
    engine: <Cpu className="w-5 h-5 text-warn" />,
    worker: <Layers className="w-5 h-5 text-purple-400" />,
    scheduler: <Clock className="w-5 h-5 text-cyan-400" />,
    telegram: <Activity className="w-5 h-5 text-blue-400" />,
  };

  const serviceNames: Record<string, { title: string; desc: string }> = {
    api: { title: "API Service", desc: "FastAPI REST & WebSocket Server" },
    ingestor: { title: "Market Ingestor", desc: "Binance WebSocket Streams & Pollers" },
    engine: { title: "Signal Engine", desc: "Multi-Indicator Confluence & Risk Evaluation" },
    worker: { title: "Worker Service", desc: "Arq Background Jobs (AI Gemini & Backtests)" },
    scheduler: { title: "Scheduler Service", desc: "Cron Automation (Market Brief & Backups)" },
    telegram: { title: "Telegram Bot", desc: "Two-way Bot Polling & Alert Dispatches" },
  };

  return (
    <div className="min-h-screen bg-bg text-fg font-sans flex flex-col">
      {/* Top Header */}
      <header className="border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-btn bg-accent/15 border border-accent/30 flex items-center justify-center text-accent shadow-sm">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-semibold text-base tracking-tight text-fg">TradeRadar</h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-surface-2 border border-border text-muted font-mono">
                v{data?.version || "0.1.0-fase0"}
              </span>
            </div>
            <p className="text-xs text-muted">Terminal Analisis Trading Real-Time (Crypto & Gold)</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-2 bg-surface-2 border border-border px-3 py-1.5 rounded-btn">
            <span
              className={`w-2 h-2 rounded-full ${
                data?.status === "healthy" ? "bg-bull animate-ping" : "bg-warn"
              }`}
            />
            <span className="text-muted">Status:</span>
            <span
              className={`font-semibold uppercase ${
                data?.status === "healthy" ? "text-bull" : "text-warn"
              }`}
            >
              {data?.status || (loading ? "MEMUAT..." : "DEGRADED")}
            </span>
          </div>

          {latencyMs !== null && (
            <div className="bg-surface-2 border border-border px-3 py-1.5 rounded-btn text-muted">
              Latensi: <span className="text-fg tabular-nums font-semibold">{latencyMs} ms</span>
            </div>
          )}

          <div className="bg-surface-2 border border-border px-3 py-1.5 rounded-btn text-muted">
            Update: <span className="text-fg">{lastChecked || "—"}</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-8 flex flex-col gap-8">
        {/* Banner Section */}
        <div className="rounded-panel border border-border bg-gradient-to-r from-surface to-surface-2 p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-lg">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-medium mb-3">
              <ShieldCheck className="w-3.5 h-3.5" />
              Fase 0 Fondasi Selesai
            </div>
            <h2 className="text-xl font-bold text-fg mb-1">
              Stack Container & Service Berjalan Normal
            </h2>
            <p className="text-sm text-muted max-w-2xl leading-relaxed">
              Arsitektur service-oriented TradeRadar siap untuk eksekusi pipeline data dan sinyal trading.
              Semua service Python berbagi package inti, saling berkomunikasi via Redis Streams, dan siap
              untuk integrasi market real di Fase selanjutnya.
            </p>
          </div>

          <button
            onClick={fetchHealth}
            className="flex items-center gap-2 bg-surface border border-border hover:bg-surface-2 text-fg text-xs font-medium px-4 py-2.5 rounded-btn transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Perbarui Status
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-panel bg-bear/10 border border-bear/30 text-bear text-sm flex items-center gap-3">
            <span className="font-bold">Koneksi Error:</span> {error}
          </div>
        )}

        {/* Infrastructure Layer Cards */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3 flex items-center gap-2">
            <Database className="w-4 h-4 text-muted" />
            Infrastruktur Penyimpanan & Event Bus
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Database Card */}
            <div className="bg-surface border border-border rounded-panel p-5 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-3.5">
                <div className="w-10 h-10 rounded-btn bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-medium text-sm text-fg">PostgreSQL 16 + TimescaleDB</h4>
                  <p className="text-xs text-muted">Hypertables & Continuous Aggregates</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-xs font-mono font-medium text-bull bg-bull/10 border border-bull/20 px-2.5 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {data?.infrastructure.database || "ONLINE"}
              </div>
            </div>

            {/* Redis Card */}
            <div className="bg-surface border border-border rounded-panel p-5 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-3.5">
                <div className="w-10 h-10 rounded-btn bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-medium text-sm text-fg">Redis 7</h4>
                  <p className="text-xs text-muted">Streams, Pub/Sub, & Heartbeat Cache</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-xs font-mono font-medium text-bull bg-bull/10 border border-bull/20 px-2.5 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {data?.infrastructure.redis || "ONLINE"}
              </div>
            </div>
          </div>
        </div>

        {/* Core Services Grid */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-muted" />
            Service Kerangka & Worker (Heartbeat Terdaftar)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.keys(serviceNames).map((key) => {
              const info = serviceNames[key];
              const svcData = data?.services?.[key];
              const isHealthy = svcData && svcData.status === "healthy";

              return (
                <div
                  key={key}
                  className="bg-surface border border-border rounded-panel p-5 flex flex-col justify-between shadow-sm hover:border-border/80 transition-all"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-btn bg-surface-2 border border-border flex items-center justify-center">
                        {serviceIcons[key] || <Activity className="w-5 h-5" />}
                      </div>
                      <div>
                        <h4 className="font-semibold text-sm text-fg">{info.title}</h4>
                        <p className="text-xs text-muted line-clamp-1">{info.desc}</p>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-border pt-3 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          isHealthy ? "bg-bull" : "bg-neutral"
                        }`}
                      />
                      <span className={isHealthy ? "text-bull font-medium" : "text-muted"}>
                        {isHealthy ? "ACTIVE" : "STANDBY"}
                      </span>
                    </div>

                    <div className="text-muted">
                      {svcData?.uptime_seconds !== undefined
                        ? `Uptime: ${Math.round(svcData.uptime_seconds)}s`
                        : "Ready"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>

      {/* Footer Disclaimer per Blueprint §8 */}
      <footer className="border-t border-border bg-surface/50 px-6 py-4 text-center text-xs text-muted">
        <p>
          TradeRadar adalah alat bantu analisis, bukan nasihat keuangan. Harga sumber data dapat
          berbeda dari broker Anda — selalu cek ulang sebelum eksekusi.
        </p>
      </footer>
    </div>
  );
}
