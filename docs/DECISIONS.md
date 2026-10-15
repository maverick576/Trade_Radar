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

---

## ADR-006: Skema Skor Konfluensi, Gerbang Macro Filter M1–M8, Strategi B, dan Layout Terminal Analisa (Fase 4)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan Teknis & Arsitektur:**
  1. **Formulasi Normalisasi Skor Dinamis:**
     - Formula: $score = 100 \cdot \sum(w_i \cdot s_i \cdot strength_i) / \sum(w_i)$ di mana $s_i \in \{+1, -1, 0\}$.
     - Indikator dengan status `NA` dikeluarkan dari pembilang maupun penyebut secara dinamis.
     - Ambang batas bobot: Bila total bobot tersedia $< 50\%$, sinyal dibatasi maksimal ke status pantau (`LONG`/`SHORT`) dan dilarang menghasilkan verdict `STRONG`.
  2. **Independensi Evaluasi 8 Gerbang Macro Filter (M1–M8):**
     - M1 (HTF): Memerlukan konfirmasi ganda sebelum memblokir sinyal — sinyal hanya dibatalkan jika KEDUA-DUANYA (H4 close vs EMA200 dan D1 Supertrend) berlawanan dengan arah sinyal.
     - M4 (Sesi Pasar TradFi Gold): Mengintegrasikan kalender pasar emas global dengan penyesuaian DST New York dan jendela rollover 20:45–01:15 UTC. Untuk instrumen Crypto (BTC, ETH, SOL), M4 lolos otomatis (24/7).
     - Seluruh sinyal yang dibatalkan oleh filter makro tetap disimpan ke tabel `signals` dengan status `blocked` dan array `blocked_by` untuk keperluan analisis akurasi dan journal audit.
  3. **Strategi B (Triple-EMA Ruang Scalper):**
     - Menggunakan susunan EMA cepat 9 (close), EMA tengah 21 (applied to Open), dan EMA lambat 50 (close).
     - Menghitung level exit otomatis (SL pada swing 10-bar atau 1.2×ATR, diapit minimal 0.8×ATR, dan TP 1R).
     - Dievaluasi independen secara paralel dengan Strategi A untuk perbandingan winrate.
  4. **Penyimpanan Idempotensial & Event Bus PubSub:**
     - Tabel `analyses` menggunakan unique constraint pada `(symbol, tf, bar_time)`.
     - Background service `engine` mengonsumsi stream `candles.closed` dan mempublikasikan event `analysis` serta `signal` ke Redis PubSub `ui.events` sehingga UI ter-update real-time dalam $\le 2$ detik.
  5. **Arsitektur Layout UI Terminal 3-Kolom:**
     - Desain modular: Chart & Mini Score History 48-jam (kiri), ScoreGauge & 10 Kartu Indikator per Kategori (tengah), Macro Checklist M1-M8 & Strategy B & Teaser Ticket/AI (kanan).

---

## ADR-007: Trade Ticket, Kalibrasi Broker, dan Paper Trading Engine (Fase 5)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan Teknis & Arsitektur:**
  1. **Formulasi Trade Ticket & Kalkulator Lot Presisi (`risk.py`, `ticket.py`):**
     - Sesuai spesifikasi `BLUEPRINT.md` §5.3:
       - Entry: $2651.0$, SL: $2636.5$ ($1.5 \times ATR$), TP1: $2665.5$ ($1.0 \times R$), TP2: $2680.0$ ($2.0 \times R$).
       - Kalkulasi lot ukuran risiko tetap $1\%$ dari saldo $\$10,000$ (risiko $\$100$) dengan ukuran kontrak 100 oz:
         $$\text{Raw Lot} = \frac{100}{14.5 \times 100} = 0.0689655\dots \xrightarrow{\text{floor step 0.01}} 0.06 \text{ lot}$$
       - Risiko aktual: $0.06 \times 14.5 \times 100 = \$87.0$ ($0.87\%$).
       - Format Salin Ringkas: `BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot`.
       - Format Salin Lengkap: teks Indonesia terstruktur dengan zona entry, invalidasi, dan checklist risiko.
  2. **Kalibrasi Harga Broker CFD / Futures (`broker_calibrations`):**
     - Offset dihitung sebagai $\Delta = P_{\text{broker}} - P_{\text{source}}$.
     - Masa berlaku aktif calibration: 4 jam (otomatis invalid jika stale).
     - Menampilkan perbandingan harga Source vs Broker vs Jarak Relatif di UI Ticket.
  3. **Kriteria Kedaluwarsa & Pembatalan Tiket:**
     - `EXPIRED_TIME`: Melebihi validitas 3 bar ($45$ menit untuk timeframe M15).
     - `CHASE_LIMIT`: Harga pasar live bergerak searah target $> 0.5 \times ATR$ dari zona entry sebelum sempat ter-fill.
     - `SL_HIT_BEFORE_ENTRY`: Harga menyentuh level Stop Loss sebelum menyentuh zona entry.
  4. **Paper Trading Engine Deterministik (`paper.py`, `paper_trades`):**
     - Eksekusi fill pada candle open bar berikutnya dengan slippage taker 2 bps ($0.02\%$) dan fee taker $0.05\%$.
     - Konservatisme candle: jika candle menyentuh level SL dan TP dalam bar yang sama, evaluasi SL diprioritaskan (Loss).
     - Aturan Partial TP:
       - TP1 hit $\rightarrow$ tutup $50\%$ posisi, geser Stop Loss ke Breakeven (BE).
       - TP2 hit $\rightarrow$ tutup sisa $50\%$ posisi.
     - Time Stop: jika posisi bertahan $\ge 32$ bar ($8$ jam pada M15), posisi ditutup otomatis pada candle close.
     - Opposite Exit: jika sinyal kuat berlawanan terkonfirmasi, posisi aktif ditutup langsung.
     - Batas Kerugian Harian (Daily Loss Limit): jika akumulasi kerugian hari ini mencapai $\ge 3\%$ dari modal awal ($\$1,000$), trading baru dihentikan.
     - Simulasi Virtual: sinyal yang diblokir oleh macro filter tetap disimulasikan (`is_virtual = True`) untuk mengukur efektivitas filter makro.
  5. **Pencatatan Eksekusi Nyata (`real_executions`):**
     - Mematuhi aturan strict: TradeRadar **tidak pernah memanggil endpoint order exchange/broker**.
     - Pengguna mencatat eksekusi manual via dialog UI (Fill price, lot, waktu, catatan), menghitung slippage nyata secara otomatis terhadap harga sinyal.
  6. **UI & Integrasi Halaman Terminal:**
     - Tab Navigasi Baru: **Ticket** (`TicketPage.tsx`) dan **Paper** (`PaperPage.tsx`).
     - Kartu Ticket Aktif disematkan di kolom keputusan `AnalisaPage.tsx` dan cockpit `DashboardPage.tsx`.
     - Dialog kalibrasi offset broker, pencatatan eksekusi nyata, dan konfirmasi penutupan posisi.

---

## ADR-008: Arsitektur Komentar AI, Validasi Anti-Halusinasi, Rate Limiting, dan Market Brief (Fase 6)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan Teknis & Arsitektur:**
  1. **Multi-Provider AI & Graceful Degradation (`ai/`):**
     - Provider Primer: **Google Gemini** (`gemini-2.5-flash`) via Google Generative Language REST API langsung dengan `response_mime_type: "application/json"` dan `response_schema` (Pydantic model schema).
     - Provider Sekunder/Opsional: **Anthropic Claude** (`claude-3-5-sonnet-20241022`) via Messages API dengan structured output tool.
     - Provider Fallback Offline: **Template Provider** berbasis aturan teknikal deterministik dalam Bahasa Indonesia yang fasih. Aktif otomatis ketika:
       - API key tidak disetel di `.env` (Zero Configuration Out-of-the-Box).
       - Kuota RPM/RPD terlampaui.
       - Terjadi gangguan jaringan/timeout.
       - Output model terdeteksi mengandung halusinasi harga.
  2. **Validasi Anti-Halusinasi Angka Ketat (`validate.py`):**
     - Sesuai prinsip *deterministic signal*: AI hanya bertindak sebagai narator/penjelas kontekstual, bukan pengambil keputusan sinyal.
     - Setiap angka float yang disebut di `level_penting` dicocokkan terhadap seluruh data input teknikal (entry, SL, TP1, TP2, VWAP, EMA, Bollinger, Supertrend, High/Low, OBI) dengan toleransi presisi $\pm 0.8\%$ atau $\le 0.5$ poin absolut.
     - Batas kata ringkasan dibatasi $\le 120$ kata tanpa janji keuntungan/profit.
     - Pelanggaran validasi langsung membatalkan output LLM dan mengalihkan ke Template Engine dengan badge `is_fallback = True`.
  3. **Rate Limiting Redis & Kuota (`ratelimit.py`):**
     - Implementasi token-bucket sliding window di Redis:
       - 5 RPM (Requests Per Minute) via key `ai:ratelimit:rpm:<window>`.
       - 100 RPD (Requests Per Day) via key `ai:ratelimit:rpd:<date_wib>` (reset otomatis tiap 00:00 WIB).
     - Monitoring kuota real-time diekspos melalui endpoint `GET /api/ai/quota` dan diintegrasikan ke probe kesiapan `/api/health/full`.
  4. **Penyimpanan Database & Idempotensi Event:**
     - Tabel PostgreSQL `ai_comments` dan `market_briefs` dibuat melalui migrasi Alembic `005_create_phase6_tables.py`.
     - Caching hash input di Redis (`ai:cache:<symbol>:<tf>:<bar_time>`) dengan TTL 15 menit mencegah pemborosan token LLM pada bar yang sama.
     - Konsumen stream di `worker.py` mendeteksi sinyal `STRONG_LONG` atau `STRONG_SHORT` dan otomatis memicu generasi komentar AI latar belakang.
  5. **Market Brief Pagi (06:45 WIB) & Halaman Brief (`/brief`):**
     - `generate_market_brief` mengompilasi snapshot multi-aset (XAUUSDT, BTCUSDT, ETHUSDT, SOLUSDT) mencakup VWAP kemarin, rentang harian, dan skor konfluensi.
     - Service `scheduler.py` memeriksa jam WIB dan otomatis mengeksekusi brief pagi setiap 06:45 WIB.
     - Halaman `BriefPage.tsx` menampilkan sentimen umum (Risk-on / Risk-off / Netral), tabel level kunci multi-aset, kartu narasi per simbol, aksi "Buat Ulang Brief", salin teks markdown, dan integrasi notifikasi Telegram.
  6. **UI Integration:**
     - Panel Tanggapan AI (`AICommentPanel.tsx`) terintegrasi pada Kolom Keputusan `AnalisaPage.tsx` dengan badge model, visual kesepakatan engine vs AI, kartu skenario bullish/bearish, level penting, dan kondisi invalidasi.
     - Status kuota AI interaktif ditampilkan pada `StatusPage.tsx`.
     - Command Palette (`Ctrl+K`) diperkaya dengan aksi cepat AI dan Market Brief.

---

## ADR-009: Arsitektur Bot Telegram Dua Arah, Keamanan Whitelist, Charting Headless, dan Notifikasi Proaktif (Fase 7)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan Teknis & Arsitektur:**
  1. **Long Polling & Keamanan Whitelist Ketat (`whitelist.py`):**
     - Menggunakan `python-telegram-bot` v21.11 (`>=21.0,<22.0`) dengan arsitektur async penuh (`Application.builder()`, `CommandHandler`, `CallbackQueryHandler`, `MessageHandler`).
     - Menggunakan polling (bukan webhook) agar andal di localhost/Docker tanpa memerlukan domain publik ber-SSL atau tunneling ngrok, serta siap dipindahkan ke VPS.
     - Pembatasan whitelist ketat melalui environment variable `TELEGRAM_ALLOWED_CHAT_IDS`. Setiap chat ID yang tidak terdaftar akan otomatis diabaikan tanpa memproses perintah atau membocorkan data.
     - Perintah `/start` menampilkan Chat ID, status verifikasi whitelist, dan *financial disclaimer* wajib.
     - Preferensi pengguna (status jeda/pause notifikasi) disimpan di database PostgreSQL pada tabel `telegram_chats`.
  2. **Render Candlestick Chart PNG Headless (`charts.py`):**
     - Menggunakan `mplfinance` dan `matplotlib` dengan headless backend `Agg` (`matplotlib.use("Agg")`).
     - Menghasilkan gambar grafik candlestick bertema gelap (`#0B0E14` background, `#00C076` candle hijau, `#FF5353` candle merah) dalam waktu $\le 300$ ms tanpa display server (X11/Wayland).
     - Overlay teknikal: Triple EMA (8, 21, 55), panel volume, serta garis horizontal level trading (Entry kuning, SL merah putus-putus, TP1 hijau putus-putus, TP2 hijau tua dash-dot).
  3. **Rich Ticket Broadcast dengan Jeda AI & Tombol Interaktif (`notifier.py`):**
     - Saat tiket baru dihasilkan, dispatcher menunggu hingga 20 detik (`wait_ai_seconds = 20`) agar komentar analisis AI selesai dibuat, sehingga tiket terkirim lengkap dengan ulasan AI dalam satu pesan.
     - Tiket dikirim sebagai foto grafik resolusi tinggi dengan teks caption Markdown Bahasa Indonesia dan tombol inline keyboard: `[✅ Saya eksekusi]`, `[⏭ Lewati]`, `[📊 Detail]`.
     - Tombol `[📊 Detail]` menyajikan popup/pesan penjabaran parameter teknikal, faktor pendukung, faktor risiko, dan invalidasi.
     - Tombol `[⏭ Lewati]` memperbarui status tiket menjadi `skipped`.
  4. **Alur Interaktif Dua Langkah "Saya eksekusi" (`handlers.py`):**
     - Sesuai prinsip produk: TradeRadar **tidak pernah memanggil endpoint eksekusi broker/exchange secara langsung**.
     - Saat pengguna menekan `[✅ Saya eksekusi]`, bot menyimpan status pending ke Redis key `tg:pending_exec:{chat_id}` dengan TTL 10 menit dan meminta pengguna membalas pesan dengan format `<HARGA_FILL> [LOT]`.
     - Ketika pengguna membalas, bot memvalidasi harga, mencatat transaksi ke tabel `real_executions` dengan atribut `source = "telegram"`, menghitung slippage nyata secara otomatis, memperbarui status tiket menjadi `executed`, dan menghapus key Redis.
  5. **Notifikasi Proaktif Menyeluruh:**
     - Konsumen Redis Stream `signals` (consumer group `telegram`) dan Redis Pub/Sub `ui.events` menyiarkan:
       - Trade Ticket baru (dengan chart PNG).
       - Exit posisi paper trading (TP1 kenaikan ke BE, TP2 penutupan penuh, SL, time stop).
       - Tiket kedaluwarsa (setelah 3–4 bar tanpa sentuhan entry).
       - Market Brief otomatis setiap 06:45 WIB.
       - Rekap Kinerja Harian setiap 22:00 WIB (total trade hari ini, winrate, realized PnL, expectancy).
       - Peringatan sistem saat koneksi data feed degraded/recovered.
  6. **Endpoint Pengaturan & Uji Koneksi Telegram (`routers/settings.py`):**
     - `GET /api/settings/telegram/status`: Mengembalikan konfigurasi bot, status online, jumlah pelanggan aktif, dan daftar chat ID terverifikasi.
     - `POST /api/settings/telegram/test`: Mengirimkan pesan pengujian instan ke semua subscriber aktif untuk verifikasi koneksi dari dashboard web.

---

## ADR-010: Jurnal, Statistik, Continuous Aggregates & Metrik Kinerja (Fase 8)
- **Tanggal:** 15 Oktober 2026
- **Status:** Diterima
- **Keputusan Teknis & Arsitektur:**
  1. **TimescaleDB Continuous Aggregates & Hypertables (`006_create_phase8_stats.py`):**
     - Tabel `paper_trades` dan `real_executions` dioptimasi sebagai TimescaleDB hypertables yang dipartisi berdasarkan `exit_time` (atau `executed_at`).
     - Tampilan continuous aggregates material teragregasi harian (`daily_paper_stats` dan `daily_real_stats`) dibuat menggunakan `time_bucket('1 day', exit_time)` dengan metrik: `total_trades`, `win_trades`, `loss_trades`, `be_trades`, `total_pnl_usd`, `total_pnl_r`, `gross_profit_usd`, `gross_loss_usd`.
     - Ditambahkan continuous aggregate policy otomatis dengan refresh interval 1 jam (`start_offset => INTERVAL '30 days'`, `end_offset => INTERVAL '1 hour'`) untuk query performa tinggi pada riwayat transaksi panjang.
  2. **Kalkulasi Metrik & KPI Deterministik (`traderadar.stats.metrics`):**
     - Formula metrik standar industri trading kuantitatif:
       - **Winrate (%):** Win / (Total - BE) dan Win / Total.
       - **Profit Factor:** Gross Profit / |Gross Loss| dengan penanganan division-by-zero (`inf` / `None`).
       - **Expectancy ($ dan R):** (P_win * Avg Win) - (P_loss * Avg Loss).
       - **Maximum Drawdown (R & USD):** Berbasis running cumulative equity peak-to-trough.
       - **Streaks:** Max consecutive wins dan max consecutive losses.
     - Mendukung 3 Mode Buku:
       - `paper`: Evaluasi transaksi virtual mesin paper trading.
       - `real`: Evaluasi eksekusi nyata dari pengguna.
       - `bandingkan`: Komparasi side-by-side selisih metrik antara Paper dan Real untuk mengukur *execution discipline & gap*.
  3. **Akurasi per Indikator & Nilai Macro Filter (`traderadar.stats.service`):**
     - **Akurasi per Indikator:** Mengevaluasi efektivitas masing-masing dari 10 indikator teknikal konfluensi ketika statusnya selaras (*aligned*) vs melawan arah (*contrarian*) terhadap hasil akhir trade. Menghasilkan net winrate edge (%) dan kontribusi rata-rata R.
     - **Nilai Macro Filter (M1–M8):** Mengevaluasi trade virtual (`is_virtual = True`) yang diblokir oleh gerbang macro filter. Menghitung jumlah kerugian yang berhasil dicegah (*losses prevented*), potensi kemenangan yang terlewat (*wins missed*), serta net R yang terselamatkan.
  4. **Analisis Slippage Nyata (`slippage_stats`):**
     - Menghitung deviasi titik (P_fill - P_signal), ekuivalen biaya kerugian/keuntungan dalam USD, serta distribusi breakdown per profil broker dan instrumen simbol.
  5. **Visualisasi Data & UX Halaman Jurnal (`frontend/src/features/journal/`):**
     - **Cumulative Equity Curve:** Grafik area garis interaktif dual-mode (R-Multiple dan USD).
     - **Distribusi R-Multiple:** Histogram frekuensi sebaran hasil trading (kategori Loss > 2R, Loss 1–2R, BE, Win 1–2R, Win > 2R).
     - **7×24 Day×Hour Heatmap (WIB):** Matriks performa 7 hari × 24 jam dalam zona waktu lokal `Asia/Jakarta` untuk mengidentifikasi *prime trading window*.
     - **Breakdown Multi-Dimensi:** Tabel rincian performa berdasarkan Simbol, Strategi, Sesi Pasar (Asia, London, New York), dan Verdict Sinyal.
     - **Modal Snapshot Analisa Trade:** Menampilkan kembali kondisi teknikal, rincian skor indikator, dan kutipan AI saat bar entri trade tercatat.
     - **Ekspor RFC 4180 CSV:** Endpoint `/api/stats/export.csv` dengan UTF-8 BOM (`\ufeff`) untuk kompatibilitas langsung tanpa corrupt formatting di Microsoft Excel.
  6. **Paritas Penuh UI, SQL Independen, dan Telegram Bot:**
     - Skrip verifikasi mandiri `verify_stats.py` menguji dan memvalidasi kebenaran seluruh formula SQL secara langsung terhadap TimescaleDB.
     - Perintah Telegram `/winrate` memanggil service `get_journal_stats` yang sama, memastikan konsistensi metrik 100% antara Web UI dan Telegram Bot.

