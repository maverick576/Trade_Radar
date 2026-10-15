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

---

## ADR-003: Arsitektur Autentikasi, Keamanan Sesi, dan Shell UI Design System (Fase 1)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan:**
  1. **Password Hashing:** Menggunakan **Argon2id** (`argon2-cffi`) dengan parameter RFC 9106 (memory_cost 65536 KiB, time_cost 3, parallelism 4) untuk keamanan maksimal terhadap GPU attack.
  2. **Stateless Access Token + Stateful Refresh Token:**
     - Access token menggunakan **PyJWT** (algoritma HS256) dengan masa berlaku 15 menit, dikirim via cookie `traderadar_access` (HttpOnly, Secure, SameSite=Lax).
     - Refresh token berupa token kriptografi acak (32 bytes urlsafe) yang disimpan sebagai hash SHA-256 di tabel PostgreSQL `refresh_tokens` dengan masa berlaku 30 hari di cookie `traderadar_refresh`. Dilengkapi mekanisme token rotation pada setiap pemanggilan `/api/auth/refresh`.
  3. **Double-Submit CSRF Protection:** Cookie `traderadar_csrf` dan header `X-CSRF-Token` divalidasi pada semua mutasi state (POST, PUT, PATCH, DELETE).
  4. **Login Brute-Force Rate Limiting:** Menggunakan Redis key `ratelimit:login:<ip>` dengan batas 5 percobaan gagal per jendela 5 menit.
  5. **Two-Factor Authentication (2FA TOTP):** Menggunakan `pyotp` (RFC 6238 standard TOTP 6 digit 30 detik) dengan provisioning URI `otpauth://` dan secret terenkripsi AES-GCM di kolom `users.totp_secret`.
  6. **FastAPI Auth Gatekeeper Middleware:** Memastikan seluruh rute `/api/*` terkunci secara default dan mengembalikan status HTTP `401 Unauthorized` dengan format error terstandarisasi, kecuali rute whitelist publik (`/api/health*`, `/api/auth/login`, `/api/auth/refresh`, `/api/docs`, `/api/openapi.json`).
  7. **Typed API Client Generation:** OpenAPI v3 schema diekstrak langsung dari FastAPI dan dikonversi ke TypeScript types menggunakan `openapi-typescript` dan `openapi-fetch` untuk menjamin kepatuhan zero `any` pada seluruh integrasi API frontend.
  8. **Design System & Aksesibilitas:** Implementasi palet tema gelap/terang (`UI_SPEC.md` §1) dengan rasio kontras WCAG AA (≥ 4.5:1 untuk teks normal), navigasi keyboard penuh (`Ctrl+K` untuk Command Palette, `1-4` untuk simbol), serta pengujian otomatis dengan `@axe-core/playwright` (0 critical/serious violations).

---

## ADR-004: Verifikasi Pasar Gold, Konektor Binance, dan Arsitektur Market Data (Fase 2)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Verifikasi & Keputusan:**
  1. **Verifikasi Asumsi Eksternal Simbol `XAUUSDT` di Binance Futures:**
     - Simbol `XAUUSDT` terverifikasi aktif di endpoint publik `https://fapi.binance.com/fapi/v1/exchangeInfo` dengan status `TRADING`, tipe kontrak `TRADIFI_PERPETUAL`, `baseAsset`: `XAU`, `quoteAsset`: `USDT`.
     - Seluruh endpoint derivatif Binance Futures untuk `XAUUSDT` berfungsi penuh dan merespons HTTP 200:
       - Kline historis (`/fapi/v1/klines?symbol=XAUUSDT&interval=15m`)
       - Orderbook depth (`/fapi/v1/depth?symbol=XAUUSDT`)
       - Open interest live (`/fapi/v1/openInterest?symbol=XAUUSDT`)
       - Histori open interest (`/futures/data/openInterestHist?symbol=XAUUSDT&period=15m`)
       - Global Long/Short Account Ratio (`/futures/data/globalLongShortAccountRatio?symbol=XAUUSDT&period=15m`)
  2. **Mitigasi DNS Poisoning ISP Lokal (Telkomsel/Internet Positif):**
     - Terdeteksi bahwa DNS bawaan ISP tertentu di Indonesia mengarahkan domain `*.binance.com` ke IP blokir `202.3.218.137`. Namun pengujian membuktikan bahwa koneksi langsung ke IP asli CloudFront/AWS tidak diblokir SNI (TLS handshake berhasil 100%).
     - Solusi arsitektural:
       - `compose.yaml` dikonfigurasi dengan `dns: [1.1.1.1, 8.8.8.8]` untuk semua service backend.
       - Modul `traderadar.core.network` menyertakan resolver DNS-over-HTTPS (DoH Cloudflare `1.1.1.1`) transparan sebagai fallback otomatis saat mendeteksi resolusi DNS lokal teracuni.
       - Fallback spot mirror ke `https://data-api.binance.vision` didukung penuh.
  3. **Rantai Fallback Sumber Gold:**
     - Urutan prioritas: `binance_futures:XAUUSDT` -> `binance_spot:PAXGUSDT` -> `oanda:XAU_USD` (opsional jika token tersedia).
     - Jika sumber aktif gagal/putus melebihi batas waktu (120 detik) atau error berturut-turut, sistem otomatis beralih ke `PAXGUSDT`, menyiarkan event status via Redis `ui.events` / WebSocket, dan menampilkan banner peringatan di UI frontend.
  4. **Kalender Sesi Pasar Gold (DST Amerika Serikat):**
     - Mengikuti jam pasar New York (`America/New_York`): buka Minggu 18:00 ET, tutup Jumat 17:00 ET.
     - Penyesuaian Daylight Saving Time (EDT UTC-4 vs EST UTC-5) dihitung secara matematis via timezone `America/New_York`.
     - Rollover harian Senin–Kamis 17:00–18:00 ET (20:45–01:15 UTC buffer) ditandai sebagai periode spread melebar untuk Macro Filter M4.
  5. **TimescaleDB Hypertable & Kompresi:**
     - Tabel `candles` dan `derivatives_snapshots` dijadikan hypertable dengan partisi waktu chunk 7 hari.
     - Kebijakan kompresi otomatis diaktifkan setelah 30 hari (`timescaledb.compress_segmentby = 'symbol, tf'`) demi efisiensi storage jangka panjang.
  6. **Pilihan Library Chart Frontend:**
     - Menggunakan `lightweight-charts` v4.2.x dari TradingView (kanvas WebGL/HTML5 berperforma tinggi, responsif, dark/light theme native).

---

## ADR-005: Formulasi Matematis 10 Indikator, Paritas TradingView, dan Zero Lookahead Bias (Fase 3)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan Teknis & Formulasi Matematis:**
  1. **Paritas Penuh Rumus TradingView & Wilder Smoothing:**
     - **RSI & Supertrend ATR:** Menggunakan *Wilder's Smoothing* (RMA, $\alpha = 1/N$, setara dengan EMA period $2N-1$), bukan Simple Moving Average atau standard exponential $\alpha = 2/(N+1)$. Hal ini memberikan kesesuaian nilai persis (toleransi $\le 0.1\%$) dengan Pine Script TradingView `ta.rsi` dan `ta.atr`.
     - **VWAP:** Dihitung dari typical price $TP = (H+L+C)/3$ dengan bobot volume, di-reset setiap hari pada pukul 00:00 UTC (awal hari kalender). Deviasi standar dihitung dengan bobot volume: $\sigma = \sqrt{\sum V (TP - VWAP)^2 / \sum V}$, menghasilkan pita $\pm 1\sigma$ dan $\pm 2\sigma$.
     - **Supertrend:** Sumber $(H+L)/2$ dengan Wilder ATR(10) dan multiplier 3.0. Arah trend mempertahankan posisi sebelumnya hingga terjadi penembusan candle close, persis seperti Pine Script Supertrend TradingView.
     - **Bollinger Bands:** SMA 20 dan standard deviation 2.0 tanpa bias ($ddof=0$). Persentil squeeze dihitung dari bandwidth 20-periode terhadap distribusi bandwidth 120 bar historis.
  2. **Jaminan Anti-Lookahead Invariant (Zero Lookahead Bias):**
     - Sesuai prinsip deterministik, perhitungan pada bar $t$ tidak boleh menggunakan informasi dari bar $t+k$ ($k > 0$).
     - **Deteksi Pivot Divergensi RSI:** Menggunakan parameter $left=5, right=3$. Sebuah bar $i$ baru dapat dikonfirmasi sebagai swing high/low setelah melewati 3 bar ke depan (yaitu pada bar $i+3$). Mesin scanner divergensi memastikan hanya pivot dengan indeks $\le t-3$ yang diikutsertakan dalam deteksi divergensi reguler pada bar $t$. Pengujian unit memvalidasi bahwa output indikator pada $df[:t]$ identik 100% dengan $df[:t+50][t]$.
  3. **Penanganan Kontinuitas Slope CVD di Batas Hari (Midnight Boundary):**
     - Untuk visualisasi grafik, garis CVD di-reset pada 00:00 UTC sesuai `SIGNAL_ENGINE.md` §3.6.
     - Namun, untuk perhitungan turunan statistik (slope regresi linier 20-bar), akumulasi volume delta dihitung secara kontinu lintas hari tanpa reset cliff drop buatan pada tengah malam. Hal ini mencegah sinyal palsu divergensi/absorpsi pada candle pertama di pergantian hari kalender UTC.
  4. **Penanganan Data Live-Only & Offline Fallback:**
     - Indikator **Orderbook Imbalance** menandai parameter `live_only=True`. Ketika dievaluasi pada data historis/backtest di mana snapshot depth offline tidak tersedia, indikator mengembalikan `status=NEUTRAL`, `strength=0.0`, dan `is_valid=False` secara anggun tanpa melempar exception atau merusak skor agregat.
     - Indikator **Sentiment Index** mengevaluasi Crypto (Fear & Greed + rasio Long/Short) dan Gold (hanya rasio Long/Short). F&G dilewati pada Gold secara deterministik.
  5. **Performa & Benchmark SLA (< 300 ms):**
     - Seluruh perhitungan dirancang berbasis vektorisasi NumPy/Pandas.
     - Hasil benchmark evaluasi lengkap 10 indikator pada 1.000 candle: **~2.1 ms per simbol/TF** (lebih dari 100x lebih cepat daripada batas SLA < 300 ms).

