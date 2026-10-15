# Changelog

Semua perubahan penting pada TradeRadar didokumentasikan di file ini.
Format mengikuti panduan [Keep a Changelog](https://keepachangelog.com/id/1.0.0/).

## [Fase 2: Data Market Real (Binance, Gold, Fallback)] - 2026-10-15

### Ditambahkan
- **Verifikasi Kontrak & Endpoints Binance (`docs/DECISIONS.md` ADR-004):**
  - Verifikasi langsung ketersediaan Binance Futures `XAUUSDT` (`status: TRADING`, `contractType: TRADIFI_PERPETUAL`, `baseAsset: XAU`, `quoteAsset: USDT`).
  - Verifikasi endpoint derivatif publik: `/fapi/v1/klines`, `/fapi/v1/depth`, `/fapi/v1/openInterest`, `/futures/data/openInterestHist`, dan `/futures/data/globalLongShortAccountRatio`.
  - Penanganan poisoning DNS ISP Indonesia (mis. Telkomsel) via DNS-over-HTTPS (DoH Cloudflare `1.1.1.1` RFC 8484) di `traderadar.core.network` dan injeksi konfigurasi DNS Docker Compose (`1.1.1.1`, `8.8.8.8`).
- **Database TimescaleDB Hypertables & Kompresi (`backend/alembic/versions/002_create_market_data_tables.py`):**
  - Hypertable `candles` dengan partisi 7 hari (`open_time`) dan kompresi kolom otomatis untuk data lebih tua dari 30 hari yang diurutkan berdasarkan `open_time DESC, symbol`.
  - Hypertable `derivatives_snapshots` untuk metrik funding rate, mark price, open interest, dan long/short ratio dengan kompresi 30 hari.
  - Tabel `sentiment_snapshots` untuk indeks Fear & Greed historis (`alternative_me`).
  - Helper batch idempotensial `upsert_candles`, `insert_derivatives_snapshot`, dan `insert_sentiment_snapshot` di `traderadar.services.candle_store` dengan sanitasi skema input.
- **Rantai Sumber Gold & Kalender Pasar (`traderadar.services.gold_source`, `traderadar.core.time`):**
  - Implementasi state machine failover `GoldSourceManager`: rantai sumber `binance_futures:XAUUSDT` → `binance_spot:PAXGUSDT` → `oanda:XAU_USD` (opsional) dengan ambang kegagalan 120 detik, pemulihan otomatis, dan publikasi event `gold_source_changed`.
  - Kalender sesi trading Gold CME/COMEX dengan deteksi US Daylight Saving Time (DST, EDT UTC-4 vs EST UTC-5), jam rollover harian (17:00–18:00 NY time / 04:00–05:00 WIB), penutupan akhir pekan (Jumat 17:00 NY s/d Minggu 18:00 NY), serta endpoint status sesi.
- **Konektor Pasar Binance Real-Time (`traderadar.services.binance`):**
  - `BinanceConnector`: koneksi WebSocket multi-stream gabungan (combined stream) untuk kline real-time (`<symbol>@kline_<tf>`), orderbook depth (`<symbol>@depth20@500ms`), dan mark price (`<symbol>@markPrice@1s`).
  - Pemulihan koneksi proaktif 23 jam (mencegah pemutusan paksa 24 jam Binance) dan reconnect eksponensial.
  - Backfill otomatis 1.000 candle historis per simbol/timeframe saat inisialisasi.
  - Deteksi gap candle otomatis (`gap_fill`) setelah reconnection atau putus jaringan > 1 periode bar.
  - Polling berkala metrik derivatif (Open Interest, Long/Short Ratio) dan Fear & Greed sentiment.
  - Pembatasan laju weight request REST (sliding window 1 menit) untuk menjaga batas limit 1200 weight/menit.
- **Service Microservice Ingestor (`traderadar.services.ingestor`):**
  - Pipeline live ingestor data market: orkestrasi backfill startup, streaming WebSocket, pemrosesan candle close, persistensi ke TimescaleDB, serta pengiriman event Redis Stream `candles.closed` dan Redis PubSub `ticks`.
- **API Market & WebSocket Server (`traderadar.api.routers.market`, `traderadar.api.routers.ws`):**
  - `GET /api/symbols`: ringkasan simbol watchlist aktif, ticker 24 jam (harga, perubahan persentase, high/low), kapabilitas indikator, status sumber Gold aktif, dan status jam sesi pasar Gold.
  - `GET /api/candles`: query data historis candle dengan filter simbol, timeframe (M15, H1, H4, D1), limit, dan kursor pagination `before`.
  - WebSocket `/ws`: koneksi dua arah real-time dengan autentikasi berbasis JWT token, subscription channel (`subscribe_ticks`, `subscribe_candles`, `subscribe_depth`), stream data tick real-time dan konfirmasi candle closed.
- **Frontend Live Market & Charting (`frontend/`):**
  - Integrasi TradingView Lightweight Charts (`lightweight-charts` v4.2.2) dengan tema gelap yang responsif dan autosizing container.
  - Komponen chart interaktif (`TradingViewChart`): candlestick series, volume histogram dengan warna selaras (naik/turun), time formatter WIB, dan update candlestick live tanpa delay.
  - `MarketContext`: state management terpusat untuk WebSocket stream, daftar simbol, active symbol selector, active timeframe selector, dan auto-reconnect WebSocket.
  - `AnalisaPage`: halaman chart live dengan toolbar pemilih timeframe (M15, H1, H4, D1), status pasar Gold (buka/tutup/rollover), banner peringatan fallback otomatis bila sumber Gold beralih, dan ringkasan metrik harga.
  - `DashboardPage`: kartu ringkasan harga live real-time untuk setiap aset watchlist dengan indikator naik/turun dan mini chart visual.
- **Pengujian & Validasi Kualitas:**
  - 39 pengujian unit & integrasi backend lulus 100% (`test_binance_connector.py`, `test_gap_fill.py`, `test_gold_fallback.py`, `test_gold_calendar.py`, `test_market_api.py`, `test_security.py`, `test_auth_api.py`).
  - Static typing & linting: 100% lulus Ruff dan Mypy Strict tanpa error pada 45 source files.
  - Frontend: 100% lulus ESLint dan TypeScript compiler (`tsc && vite build`).
  - Verifikasi kontainer Docker Desktop: 16 hypertable partitions terisi penuh 1.000 candle real dari Binance API, snapshots derivatif aktif terisi, dan kontainer berjalan healthy.

## [Fase 1: Auth & Shell UI Profesional] - 2026-10-15

### Ditambahkan
- **Database & Migrasi Alembic (`backend/alembic/`):**
  - Model SQLAlchemy DeclarativeBase di `traderadar.core.models`: `users`, `refresh_tokens`, `audit_log`, `app_settings`, dan `telegram_chats`.
  - Migrasi Alembic async `001_create_auth_tables.py` untuk pembuatan skema tabel auth.
  - Service `traderadar.services.migrate`: eksekusi migrasi otomatis saat startup container dan seeding admin user default dari variabel lingkungan (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) secara idempotensial disertai pencatatan audit log `user.create`.
- **Backend Autentikasi & Keamanan (`traderadar.core.security` & `traderadar.api`):**
  - Argon2id password hashing dan verifikasi timing-attack safe.
  - JWT Stateless Access Token (15 menit) dan Opaque Refresh Token SHA-256 (30 hari) di tabel `refresh_tokens` dengan rotasi token.
  - Double-Submit CSRF cookie (`traderadar_csrf`) dan validasi header `X-CSRF-Token` pada mutasi state HTTP.
  - Rate Limiting login gagal di Redis (`ratelimit:login:<ip>`, maksimum 5 percobaan per 5 menit) dengan audit log `user.login_blocked`.
  - Two-Factor Authentication (2FA TOTP RFC 6238) via `pyotp` (setup QR URI, verify token, enable, disable) dengan secret AES-GCM terenkripsi.
  - Endpoint REST API `/api/auth`: `/login`, `/logout`, `/refresh`, `/me`, `/password`, `/totp/setup`, `/totp/verify`, `/totp/disable`.
  - Global Gatekeeper Middleware di FastAPI: memblokir akses endpoint terlindungi `/api/*` tanpa autentikasi valid dan mengembalikan `401 Unauthorized` dengan skema error konsisten.
  - Error handler terpusat untuk `HTTPException`, `RequestValidationError`, dan exception tak tertangani.
  - Script generator `traderadar.api.dump_openapi` untuk mengekspor skema OpenAPI ke frontend.
- **Frontend Design System & Shell (`frontend/`):**
  - Implementasi Design System profesional (`UI_SPEC.md` §1) dengan dukungan tema Gelap/Terang/Auto (`ThemeProvider`), palet warna berstandar rasio kontras WCAG AA (≥ 4.5:1), font Inter dan JetBrains Mono tabular.
  - Komponen UI atomik dapat diakses: `Button`, `Input` (label, floating show/hide toggle, pesan error aksesibel), `Card`, `Badge`, `Dialog`.
  - Shell aplikasi modern:
    - Sidebar kiri dapat diciutkan/dilebarkan (`Sidebar`) dengan navigasi 9 menu utama.
    - Topbar profesional (`Topbar`): pemilih simbol cepat (`XAUUSDT`, `BTCUSDT`, `ETHUSDT`, `SOLUSDT` dengan shortcut angka `1-4`), indikator status koneksi real-time dengan ping latency, jam WIB live, tombol pemilih tema, dan dropdown menu akun pengguna.
    - Palet Perintah (`CommandPalette` / `Ctrl+K` atau `/`) dengan pencarian instan untuk navigasi menu, pemilihan simbol, aksi cepat AI Brief, dan kalibrasi broker.
    - Modal interaktif: Ganti Kata Sandi (`PasswordModal`) dan Pengaturan 2FA TOTP (`TotpModal`) dengan manual secret key copy dan link `otpauth://`.
  - Halaman Otentikasi (`LoginPage`) yang elegan dengan kartu terpusat, feedback error rate-limit, dan validasi form penuh.
  - Halaman Status Layanan Cockpit (`StatusPage`): pemantauan real-time REST latency, TimescaleDB hypertable, Redis Streams, dan ke-6 container microservice dengan indikator visual dan refresh otomatis.
  - Typed API Client: generate otomatis tipe TypeScript dari OpenAPI (`npm run gen:api`) menggunakan `openapi-typescript` dan `openapi-fetch` dengan injeksi otomatis CSRF token dan cookies credentials.
- **Pengujian & Kualitas (Testing & CI):**
  - Backend: 23 unit & integration test pytest (`test_security.py` dan `test_auth_api.py`) dengan coverage keamanan tinggi.
  - Frontend: Unit test React (`App.test.tsx`) di Vitest dan 0 pelanggaran ESLint.
  - E2E Playwright: 4 skenario komprehensif (`auth.spec.ts`) yang memverifikasi gatekeeper 401, audit aksesibilitas Axe-Core (0 pelanggaran kritikal/serius, kepatuhan WCAG AA / Lighthouse Accessibility ≥ 95), validasi kredensial salah, dan siklus login/logout serta navigasi shell cockpit.

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
