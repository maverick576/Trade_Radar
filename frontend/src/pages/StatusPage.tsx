import React, { useEffect, useState, useCallback } from "react";
import {
  Activity,
  Database,
  Layers,
  Cpu,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Server,
  Zap,
  Bot,
  Sparkles,
  Clock,
  Radio,
} from "lucide-react";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { api, type FullHealthResponse } from "../api/client";

interface ServiceInfo {
  id: string;
  name: string;
  description: string;
  memoryLimit: string;
}

const SERVICE_REGISTRY: ServiceInfo[] = [
  {
    id: "api",
    name: "API & WebSocket",
    description: "REST API FastAPI, autentikasi sesi, validasi, dan event pub/sub",
    memoryLimit: "384 MB",
  },
  {
    id: "ingestor",
    name: "Market Ingestor",
    description: "Konektor Binance WebSocket, depth20, funding rate, dan open interest",
    memoryLimit: "384 MB",
  },
  {
    id: "engine",
    name: "Signal & Confluence Engine",
    description: "Kalkulasi 10 indikator, Strategi B, macro filter, ticket, dan paper trader",
    memoryLimit: "512 MB",
  },
  {
    id: "worker",
    name: "Async Job Worker",
    description: "Komentar AI Gemini (arq queue), ML training, dan render chart PNG",
    memoryLimit: "1024 MB",
  },
  {
    id: "scheduler",
    name: "Scheduler & Cron",
    description: "Market Brief otomatis 06:45 WIB, kalender berita, dan backup harian",
    memoryLimit: "128 MB",
  },
  {
    id: "telegram",
    name: "Telegram Bot",
    description: "Bot interaktif dua arah, notifikasi sinyal, dan alur eksekusi broker",
    memoryLimit: "192 MB",
  },
];

export const StatusPage: React.FC = () => {
  const [healthData, setHealthData] = useState<FullHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [latency, setLatency] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchHealth = useCallback(async () => {
    const startTime = performance.now();
    try {
      const { data, error } = await api.GET("/api/health/full");
      const elapsed = Math.round(performance.now() - startTime);
      setLatency(elapsed);

      if (data && !error) {
        setHealthData(data);
        setLastUpdated(new Date());
      }
    } catch {
      // Failed to reach
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHealth();
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      void fetchHealth();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchHealth, autoRefresh]);

  const isHealthy = healthData?.status === "healthy";
  const servicesMap = healthData?.services || {};

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Page Title & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold tracking-tight text-fg flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-accent" aria-hidden="true" />
            <span>Status Layanan & Arsitektur</span>
          </h1>
          <p className="text-xs text-muted mt-1">
            Pemantauan kesehatan real-time kontainer Docker, event stream, dan konektivitas data.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`text-xs px-3 py-1.5 rounded-btn border transition-colors flex items-center gap-2 ${
              autoRefresh
                ? "bg-accent/10 border-accent/30 text-accent font-medium"
                : "bg-surface-2 border-border text-muted"
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${autoRefresh ? "animate-pulse" : ""}`} aria-hidden="true" />
            <span>{autoRefresh ? "Auto-refresh Aktif" : "Auto-refresh Mati"}</span>
          </button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => void fetchHealth()}
            loading={loading}
            className="text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
            Segarkan
          </Button>
        </div>
      </div>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Status Sistem */}
        <Card className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${
              isHealthy ? "bg-bull/15 text-bull" : "bg-warn/15 text-warn"
            }`}
          >
            {isHealthy ? (
              <CheckCircle2 className="w-6 h-6" aria-hidden="true" />
            ) : (
              <AlertTriangle className="w-6 h-6" aria-hidden="true" />
            )}
          </div>
          <div>
            <span className="text-xs text-muted font-medium block">Kondisi Sistem</span>
            <span className="text-lg font-bold text-fg capitalize">
              {healthData?.status === "healthy" ? "Normal & Siap" : "Degraded"}
            </span>
            <span className="text-[11px] text-muted block mt-0.5">Semua proses aktif</span>
          </div>
        </Card>

        {/* Latensi API */}
        <Card className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-accent/15 text-accent flex items-center justify-center shrink-0">
            <Zap className="w-6 h-6" aria-hidden="true" />
          </div>
          <div>
            <span className="text-xs text-muted font-medium block">Latensi Probe REST</span>
            <span className="text-lg font-bold font-mono text-fg tabular-nums">
              {latency !== null ? `${latency} ms` : "..."}
            </span>
            <span className="text-[11px] text-muted block mt-0.5">Respon HTTP lokal</span>
          </div>
        </Card>

        {/* Database & Storage */}
        <Card className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-bull/15 text-bull flex items-center justify-center shrink-0">
            <Database className="w-6 h-6" aria-hidden="true" />
          </div>
          <div>
            <span className="text-xs text-muted font-medium block">TimescaleDB Hypertable</span>
            <span className="text-lg font-bold text-fg">
              {healthData?.infrastructure?.database === "healthy" ? "Terhubung" : "Terputus"}
            </span>
            <span className="text-[11px] text-muted block mt-0.5">Postgres 16 · Chunk 7h</span>
          </div>
        </Card>

        {/* Redis Streams Bus */}
        <Card className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-accent/15 text-accent flex items-center justify-center shrink-0">
            <Layers className="w-6 h-6" aria-hidden="true" />
          </div>
          <div>
            <span className="text-xs text-muted font-medium block">Event Bus (Redis)</span>
            <span className="text-lg font-bold text-fg">
              {healthData?.infrastructure?.redis === "healthy" ? "Aktif" : "Terputus"}
            </span>
            <span className="text-[11px] text-muted block mt-0.5">Streams + Pub/Sub</span>
          </div>
        </Card>
      </div>

      {/* Service Containers Grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-muted flex items-center gap-2">
            <Server className="w-4 h-4 text-accent" aria-hidden="true" />
            <span>Kontainer Layanan TradeRadar ({SERVICE_REGISTRY.length})</span>
          </h2>
          {lastUpdated && (
            <span className="text-xs text-muted flex items-center gap-1.5 font-mono">
              <Clock className="w-3.5 h-3.5" aria-hidden="true" />
              Diperbarui: {lastUpdated.toLocaleTimeString("id-ID")} WIB
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SERVICE_REGISTRY.map((srv) => {
            const rawStatus = servicesMap[srv.id as keyof typeof servicesMap];
            const isOnline = rawStatus && typeof rawStatus === "object" && "status" in rawStatus;

            return (
              <Card key={srv.id} className="relative flex flex-col justify-between hover:border-muted/50 transition-colors">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-accent" aria-hidden="true" />
                      <span className="font-semibold text-sm text-fg">{srv.name}</span>
                    </div>
                    <Badge variant={isOnline ? "bull" : "bear"} dot>
                      {isOnline ? "Online" : "Unreachable"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted leading-relaxed mb-4">{srv.description}</p>
                </div>

                <div className="pt-3 border-t border-border flex items-center justify-between text-[11px] text-muted font-mono">
                  <span>Alokasi: {srv.memoryLimit}</span>
                  <span className="text-fg font-medium">Service: {srv.id}</span>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* External Integration & Data Pipeline Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Market Data Integrations */}
        <Card>
          <h2 className="text-sm font-bold text-fg mb-3 flex items-center gap-2">
            <Radio className="w-4 h-4 text-accent" aria-hidden="true" />
            <span>Rantai Sumber Data Pasar</span>
          </h2>
          <div className="space-y-3">
            <div className="p-3 rounded-btn bg-surface-2 border border-border flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-fg block">Gold Perpetual (XAUUSDT)</span>
                <span className="text-[11px] text-muted block mt-0.5">
                  Binance USDT-M Futures · 15m/1h/4h/1d + depth20
                </span>
              </div>
              <Badge variant="bull" dot>
                Primer Aktif
              </Badge>
            </div>

            <div className="p-3 rounded-btn bg-surface-2 border border-border flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-fg block">Gold Fallback (PAXGUSDT)</span>
                <span className="text-[11px] text-muted block mt-0.5">
                  Binance Spot · Switch otomatis bila XAUUSDT terputus &gt; 2 mnt
                </span>
              </div>
              <Badge variant="neutral">Standby</Badge>
            </div>

            <div className="p-3 rounded-btn bg-surface-2 border border-border flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-fg block">Crypto Majors (BTC, ETH, SOL)</span>
                <span className="text-[11px] text-muted block mt-0.5">
                  Binance Futures combined stream · CVD taker volume
                </span>
              </div>
              <Badge variant="bull" dot>
                Aktif
              </Badge>
            </div>
          </div>
        </Card>

        {/* AI & Telegram Channels */}
        <Card>
          <h2 className="text-sm font-bold text-fg mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" aria-hidden="true" />
            <span>AI Gemini & Bot Telegram</span>
          </h2>
          <div className="space-y-3">
            <div className="p-3 rounded-btn bg-surface-2 border border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-fg">Google Gemini (3.8 Flash)</span>
                <Badge variant="accent">Rate Limit: 5 RPM / 100 RPD</Badge>
              </div>
              <div className="w-full bg-surface h-2 rounded-full overflow-hidden border border-border mb-1">
                <div className="bg-accent h-full rounded-full transition-all duration-300" style={{ width: "8%" }} />
              </div>
              <div className="flex items-center justify-between text-[11px] text-muted">
                <span>Penggunaan token hari ini</span>
                <span className="font-mono">8 / 100 Permintaan</span>
              </div>
            </div>

            <div className="p-3 rounded-btn bg-surface-2 border border-border flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Bot className="w-4 h-4 text-muted" aria-hidden="true" />
                <div>
                  <span className="text-xs font-semibold text-fg block">Bot Telegram Dua Arah</span>
                  <span className="text-[11px] text-muted block">Polling, notifikasi sinyal, dan Trade Ticket</span>
                </div>
              </div>
              <Badge variant="neutral">Siap</Badge>
            </div>

            <div className="p-3 rounded-btn bg-surface-2 border border-border flex items-center justify-between text-xs">
              <span className="text-muted">Versi Build Aplikasi</span>
              <span className="font-mono font-medium text-fg">{healthData?.version || "0.1.0-dev"}</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
