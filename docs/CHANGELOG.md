# Changelog

Semua perubahan penting pada TradeRadar didokumentasikan di file ini.
Format mengikuti panduan [Keep a Changelog](https://keepachangelog.com/id/1.0.0/).

## [Fase 0: Fondasi, Docker, CI] - 2026-10-15

### Ditambahkan
- **Struktur Repositori & Proyek:**
  - Setup uv package manager Python 3.12 dengan `pyproject.toml` dan `uv.lock`.
  - Setup React 18 + TypeScript (strict) + Vite 6 di direktori `frontend/`.
  - Konfigurasi linting & formatting: Ruff, Mypy (`strict = true`), ESLint, dan Prettier.
  - Setup `.pre-commit-config.yaml` dan `.gitignore`.
- **Infrastruktur & Docker Desktop:**
  - `compose.yaml` produksi-lokal dan `compose.dev.yaml` development override.
  - Multi-stage `infra/docker/python.Dockerfile` dengan uv pre-caching dan user non-root `app`.
  - Multi-stage `infra/docker/web.Dockerfile` dengan node builder dan image Caddy server.
  - `infra/caddy/Caddyfile` reverse proxy `/api/*`, `/ws`, static asset gzip/zstd, dan header keamanan CSP.
  - `infra/postgres/init.sql` untuk inisialisasi ekstensi TimescaleDB.
  - Pinning versi image spesifik (`timescaledb:2.18.2-pg16`, `redis:7.4.2-alpine`, `caddy:2.9.1-alpine`, `python:3.12-slim`, `node:22.14-alpine`).
- **Core Backend (`traderadar.core`):**
  - `config.py`: Validasi Pydantic v2 untuk `.env` (`EnvSettings`) dan `settings.yaml` (`AppSettings` dengan batas watchlist ≤ 5).
  - `logging.py`: Structlog terstruktur JSON untuk produksi dengan penyembunyian otomatis kunci sensitif (password, secret, token).
  - `db.py`: Async connection pool SQLAlchemy 2 + asyncpg untuk PostgreSQL/TimescaleDB.
  - `redis.py`: Async connection pool Redis, heartbeat writer/reader, dan ping healthcheck.
  - `events.py`: Skema Pydantic untuk event `candles.closed`, `signals`, `ticks`, `ui.events`, dan `ServiceHeartbeat`.
  - `time.py`: Utilitas waktu standar UTC internal dan konversi presentasi WIB (`Asia/Jakarta`).
- **Service Kerangka & Healthcheck:**
  - Service entrypoints: `api`, `ingestor`, `engine`, `worker`, `scheduler`, `telegram`, dan `migrate`.
  - ServiceRunner dengan heartbeat otomatis setiap 10 detik ke Redis `status:<service>` dan penanganan graceful shutdown.
  - Endpoint liveness `/api/health` dan readiness `/api/health/full` yang merangkum status DB, Redis, dan seluruh container.
  - CLI `healthcheck.py` untuk `HEALTHCHECK` docker container.
- **Frontend Placeholder & Status Cockpit:**
  - Design system dark mode modern (`#0B0E14`, `#121722`, border `#232A3A`, aksen `#3B82F6`).
  - Halaman status interaktif yang menampilkan kesehatan real-time, latensi ms, uptime, dan seluruh service.
- **Skrip Pembungkus Windows:**
  - `start.bat`, `stop.bat`, `logs.bat`, `update.bat`, `backup.bat`, `reset-data.bat` dengan pesan ramah Bahasa Indonesia.
- **Dokumentasi & CI:**
  - `docs/DECISIONS.md` untuk catatan keputusan arsitektur (ADR).
  - Workflow GitHub Actions `.github/workflows/ci.yml` (linting ruff/mypy/eslint, unit testing pytest/vitest, dan build image docker).
