# Catatan Keputusan Teknis (Architecture Decision Records)

Dokumen ini mencatat keputusan teknis, pinning versi, dan verifikasi asumsi eksternal per fase.

---

## ADR-001: Pilihan Pin Versi Docker Image & Runtime (Fase 0)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima

### Pilihan Versi Image:
1. **Python Base:** `python:3.12-slim` (runtime stabil untuk package backend FastAPI & ML LightGBM).
2. **uv Package Manager:** `ghcr.io/astral-sh/uv:0.6.14` (instalasi dependency Python berkecepatan tinggi dan reproduktif).
3. **TimescaleDB:** `timescale/timescaledb:2.18.2-pg16` (PostgreSQL 16 LTS dengan extension TimescaleDB v2.18.2 untuk hypertable market data).
4. **Redis:** `redis:7.4.2-alpine` (Redis versi 7.4 stabil untuk Redis Streams dan Pub/Sub).
5. **Caddy:** `caddy:2.9.1-alpine` (Web server reverse proxy cepat, ringan, otomatis HTTPS, CSP headers).
6. **Node.js (Builder Web):** `node:22.14-alpine` (Node 22 LTS untuk Vite + React 18).

### Pilihan Versi Frontend:
- React: `18.3.1` (kompatibel dengan ecosystem charting TradingView Lightweight Charts).
- Vite: `6.1.0`
- Tailwind CSS: `3.4.17`
- TypeScript: `5.7.3` (strict mode tanpa `any`).

### Pilihan Versi Backend:
- Python 3.12 dengan `uv` lockfile (`uv.lock`).
- FastAPI `0.115.x`, SQLAlchemy `2.0.x` asyncpg, Pydantic v2 `2.10.x`, Structlog `25.1.x`.

---

## ADR-002: Arsitektur Healthcheck & Heartbeat (Fase 0)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan:**
  - Setiap service kerangka (`ingestor`, `engine`, `worker`, `scheduler`, `telegram`) mengirim heartbeat berkala ke Redis key `status:<service>` dengan TTL 30 detik.
  - CLI `python -m traderadar.healthcheck` digunakan oleh Docker compose healthcheck:
    - `api`: mengecek HTTP status `http://127.0.0.1:8000/api/health`
    - `service <nama>`: mengecek kesegaran heartbeat di Redis (< 45s).
  - Endpoint `/api/health/full` merangkum status DB, Redis, dan seluruh heartbeat service untuk konsumsi UI dan monitoring.
