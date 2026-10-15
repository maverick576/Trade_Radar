# TradeRadar — Blueprint Web App Analisis Trading

Versi 2.0 · Oktober 2026 · Target: aplikasi web profesional yang berjalan di **Docker Desktop** pada PC Windows user, siap dipindah ke VPS tanpa perubahan arsitektur.

> **Perubahan dari v1:** MT5 dihapus total, semua data dari web API; stack dipecah menjadi container Docker; Postgres/TimescaleDB + Redis; login admin; fitur **Trade Ticket** & **Market Brief** untuk eksekusi manual di broker.

---

## 1. Ringkasan Produk

TradeRadar memantau 3–5 simbol (crypto + Gold) secara real-time dari web, menjalankan dua strategi hasil analisis video referensi, lalu menyajikan **resume siap eksekusi** (Trade Ticket) yang user salin ke broker (mis. Exness) secara manual.

| Sumber | Metode | Peran di aplikasi |
|---|---|---|
| Video 1 — Bot crypto ETH/USDT | 10 indikator lintas 6 kategori + macro filter + voting + LightGBM | **Strategi A: "Konfluensi-10"** (utama) |
| Video 2 — Ruang Scalper Gold | 3 EMA (cepat / EMA21 applied-to-Open / lambat) + konfirmasi multi-TF + TP/SL tetap | **Strategi B: "Triple-EMA"** (pembanding) |

### Keputusan yang dikunci (dari user)
- **Semua data dari web.** Tidak ada koneksi MetaTrader. User mengeksekusi manual dari Trade Ticket.
- **Market:** crypto & Gold dari **Binance USDT-M Futures** (data publik, tanpa API key).
  - Crypto: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
  - Gold: **`XAUUSDT` perpetual** (kontrak emas Binance, rilis Jan 2026). Fallback otomatis `PAXGUSDT` (token emas spot). Opsional upgrade: OANDA practice API (`XAU_USD` spot) bila user mengisi token.
- **Eksekusi:** sinyal + paper trading + Trade Ticket untuk eksekusi manual. Tidak ada order otomatis ke exchange/broker mana pun.
- **AI:** Gemini API (provider-agnostic; Claude & template sebagai cadangan).
- **Fitur:** Telegram dua arah, Jurnal & statistik winrate, Kalender berita, Backtesting.
- **Gaya:** intraday — entry M15, konfirmasi H1, bias H4/D1.
- **Runtime:** Docker Desktop (WSL2), PC 16 GB RAM → anggaran total container ≤ 4 GB.
- **Login:** satu akun admin.
- Kualitas: **profesional** (pengerjaan oleh agent) — kode bertipe, teruji, terdokumentasi, UI setara produk SaaS.

### Sengaja TIDAK dimasukkan
- Auto-trading uang nyata · multi-user/role · scraping Twitter/X · email/Discord · Kubernetes · SSR (Next.js) — dashboard privat tidak butuh SEO; SPA + API lebih sederhana dipelihara.

---

## 2. Arsitektur

**Pola:** service-oriented ringan dalam satu `docker compose`, berkomunikasi lewat **Redis** (Streams untuk event penting, Pub/Sub untuk tick) dan **PostgreSQL + TimescaleDB** sebagai penyimpanan. Semua service Python berbagi satu codebase/package (`traderadar`) dengan entrypoint berbeda → tidak ada duplikasi logika.

```
                  Browser  ──►  http://localhost:8080
                                   │
                          ┌────────▼────────┐
                          │  proxy (Caddy)  │  static SPA + reverse proxy /api /ws
                          └───┬─────────┬───┘
                    /api,/ws  │         │ /
                    ┌─────────▼───┐   ┌─▼───────────┐
                    │ api         │   │ web (build) │ React+TS (di-serve Caddy)
                    │ FastAPI     │   └─────────────┘
                    └──┬───────▲──┘
         SQL           │       │ Redis pub/sub (tick, analysis, signal → WS)
   ┌───────────────────▼─┐   ┌─┴─────────────────────────────────────────┐
   │ db                  │   │ redis                                     │
   │ Postgres16+Timescale│◄─►│ Streams: candles.closed, signals, jobs    │
   └───────▲─────────────┘   └──▲──────────▲───────────▲──────────▲──────┘
           │                    │          │           │          │
   ┌───────┴──────┐   ┌─────────┴──┐ ┌─────┴──────┐ ┌──┴───────┐ ┌┴──────────┐
   │ ingestor     │   │ engine     │ │ worker     │ │ telegram │ │ scheduler │
   │ Binance WS   │   │ indikator  │ │ (arq)      │ │ bot long │ │ (arq cron)│
   │ + pollers    │   │ skor/macro │ │ AI Gemini  │ │ polling  │ │ news, brief│
   │ news, F&G    │   │ paper trade│ │ backtest   │ │          │ │ retrain,   │
   └──────┬───────┘   │ tickets    │ │ ML train   │ └────┬─────┘ │ backup     │
          │           └────────────┘ └─────┬──────┘      │       └───────────┘
          ▼                                ▼             ▼
   Binance fapi/fstream · alternative.me · ForexFactory JSON · Gemini · Telegram · (OANDA opsional)
```

### Service & anggaran memori (limit di compose)
| Service | Image/basis | Tugas | Mem limit |
|---|---|---|---|
| `proxy` | `caddy:2-alpine` | Serve SPA, reverse proxy, header keamanan, gzip | 64 MB |
| `api` | `traderadar-py` | REST + WebSocket, auth, validasi | 384 MB |
| `ingestor` | `traderadar-py` | WS kline/depth Binance, poll funding/OI/LS, F&G, kalender; tulis DB, publish Redis | 384 MB |
| `engine` | `traderadar-py` | Konsumsi `candles.closed` → analisis, skor, macro filter, sinyal, ticket, paper trader | 512 MB |
| `worker` | `traderadar-py` | Job arq: komentar AI, backtest, training LightGBM, render chart PNG | 1 GB |
| `scheduler` | `traderadar-py` | arq cron: refresh berita, Market Brief, rekap harian, retrain mingguan, backup | 128 MB |
| `telegram` | `traderadar-py` | Bot dua arah (long polling) | 192 MB |
| `db` | `timescale/timescaledb:latest-pg16` (pin tag) | Data | 768 MB |
| `redis` | `redis:7-alpine` | Event bus, cache, antrean | 128 MB |
| `migrate` | `traderadar-py` | One-shot `alembic upgrade head` + seed admin | — |
| *(profil `monitoring`)* `prometheus`, `grafana` | resmi | Metrik opsional | 512 MB |

Total default ≈ 3,6 GB. Detail compose ada di `INFRA_DOCKER.md`.

### Alur utama (live)
1. `ingestor` menerima kline M15/H1/H4/D1 via combined WebSocket → upsert hypertable `candles` → saat bar close, `XADD candles.closed`.
2. `engine` (consumer group) menghitung 10 indikator + Strategi B → simpan `analyses` → publish `analysis` (UI live).
3. Bila verdict `STRONG_*` dan macro filter PASS → buat `signal` + **Trade Ticket** → `paper trader` membuka posisi simulasi → `XADD signals`.
4. `worker` mengambil job `ai_comment` (rate-limited) → Gemini → simpan → publish `ai_comment`.
5. `telegram` mengonsumsi `signals` (+ komentar AI bila siap dalam 20 dtk) → kirim ticket + chart + tombol.
6. `engine` memantau `ticks` → TP/SL paper → update jurnal → publish `trade`.
7. Preview skor live tiap 5 dtk (label "LIVE · belum close") hanya untuk UI; tidak pernah memicu sinyal.

Idempotensi: setiap event membawa `event_id` (`{symbol}:{tf}:{bar_time}`); konsumer melakukan upsert sehingga restart/replay aman.

---

## 3. Tech Stack

### Backend (Python 3.12, satu package `traderadar`)
| Kebutuhan | Pilihan |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2, `pydantic-settings` |
| DB | SQLAlchemy 2 async + `asyncpg`, Alembic, TimescaleDB hypertable & continuous aggregates |
| Event/antrean | `redis` (asyncio), Redis Streams, **arq** untuk job & cron |
| Market data | `httpx`, `websockets` — konektor ditulis sendiri (tanpa SDK pihak ketiga) |
| Analitik | `pandas`, `numpy` — indikator ditulis sendiri & diuji |
| ML | `lightgbm`, `scikit-learn`, `joblib` |
| AI | `google-genai` (Gemini), opsional `anthropic` |
| Telegram | `python-telegram-bot` ≥ 21 |
| Chart PNG | `mplfinance` |
| Auth | `argon2-cffi`, JWT di cookie httpOnly (`pyjwt`), CSRF double-submit, `pyotp` (2FA opsional) |
| Observability | `structlog` (JSON log), `prometheus-client`, endpoint `/metrics` |
| Kualitas | `ruff`, `mypy --strict` (paket `engine/`), `pytest`, `pytest-asyncio`, `respx`, `testcontainers` |
| Paket | `uv` + `uv.lock` |

### Frontend (detail di `UI_SPEC.md`)
React 18 + TypeScript (strict) + Vite · Tailwind CSS + **shadcn/ui** (Radix) · TanStack Query + TanStack Router · Zustand · `lightweight-charts` (TradingView) · Recharts · `lucide-react` · `react-hook-form` + Zod · klien API dibangkitkan dari OpenAPI (`openapi-typescript` + `openapi-fetch`) · Vitest + Testing Library · Playwright (e2e) · ESLint + Prettier.

### Infra
Docker Compose v2 · Caddy · Postgres 16 + TimescaleDB · Redis 7 · GitHub Actions (lint, test, build image) · pre-commit.

---

## 4. Struktur Repositori

```
05_Apps_Analisis_Trade/
├─ AGENTS.md
├─ README.md
├─ compose.yaml                 # stack produksi-lokal
├─ compose.dev.yaml             # override: hot reload, port debug
├─ .env.example
├─ start.bat / stop.bat / update.bat / logs.bat   # pembungkus docker compose untuk user
├─ config/settings.example.yaml
├─ docs/                        # blueprint
├─ infra/
│  ├─ caddy/Caddyfile
│  ├─ docker/python.Dockerfile  # multi-stage, non-root
│  ├─ docker/web.Dockerfile     # build SPA → disalin ke image Caddy
│  ├─ postgres/init.sql         # extension timescaledb
│  └─ monitoring/ (prometheus.yml, grafana dashboards)
├─ backend/
│  ├─ pyproject.toml, uv.lock
│  ├─ alembic/
│  ├─ src/traderadar/
│  │  ├─ core/        # config, logging, db, redis, events (schemas & stream names), security, time
│  │  ├─ market/      # connectors/binance.py, connectors/oanda.py (opsional), symbols.py, candle_repo.py
│  │  ├─ engine/      # indicators/*, analysis.py, scoring.py, macro_filter.py, risk.py, ticket.py,
│  │  │               # strategies/{konfluensi10,triple_ema}.py, paper/trader.py
│  │  ├─ ml/          # features, labeling, train, registry
│  │  ├─ ai/          # base, gemini, claude, template, prompts, ratelimit, validate
│  │  ├─ news/        # service, sources/{forexfactory,finnhub}
│  │  ├─ telegram/    # bot, handlers, formatters, charts
│  │  ├─ backtest/    # data_loader, runner, report, walkforward
│  │  ├─ stats/       # jurnal & metrik
│  │  ├─ api/         # app.py, deps.py, routers/*, ws.py
│  │  └─ services/    # entrypoints: ingestor.py, engine.py, worker.py, scheduler.py, telegram.py
│  └─ tests/ (unit/, integration/, fixtures/)
├─ frontend/
│  ├─ package.json, vite.config.ts
│  └─ src/ (app/, routes/, features/<domain>/, components/ui/, lib/, api/generated/)
└─ .github/workflows/ci.yml
```

Volume Docker bernama: `pgdata`, `redisdata`, `models`, `backups` (folder `./backups` di-bind agar user bisa melihat file backup).

---

## 5. Modul — Tanggung Jawab & Kontrak

### 5.1 Market data (`ingestor`)
- **BinanceConnector (USDT-M Futures, publik):**
  - Saat start: validasi simbol via `GET /fapi/v1/exchangeInfo` (status `TRADING`, tick size, step size). **Agent wajib memverifikasi `XAUUSDT` ada di respons**; bila tidak, pakai fallback (lihat di bawah) dan catat di `docs/DECISIONS.md`.
  - Backfill 1000 bar per (simbol, TF) → hypertable `candles`.
  - Live: satu combined stream `<sym>@kline_15m|1h|4h|1d` + `<sym>@depth20@500ms` + `<sym>@markPrice@1s` (funding & mark realtime).
  - Poll REST: open interest history & long/short ratio (5 mnt), Fear & Greed (1 jam).
  - Reconnect exponential backoff (1→60 dtk), deteksi gap → backfill parsial. Binance memutus koneksi WS setiap 24 jam → reconnect terjadwal sebelum itu.
  - Hormati weight limit (`X-MBX-USED-WEIGHT-1M`); throttle bila > 70%.
- **Rantai sumber Gold** (konfigurasi `gold.sources` berurutan):
  1. `binance_futures:XAUUSDT` (default, lengkap: kline, taker volume, funding, OI, orderbook).
  2. `binance_spot:PAXGUSDT` (fallback otomatis bila #1 tidak tersedia/terputus > 2 mnt).
  3. `oanda:XAU_USD` (opsional; aktif bila `OANDA_API_TOKEN` diisi; harga spot paling dekat dengan broker CFD).
  Sumber aktif selalu tampil di UI ("Sumber: Binance XAUUSDT").
- **Fallback jaringan crypto:** bila `fapi.binance.com` tidak terjangkau → spot `api.binance.com` → `data-api.binance.vision`; indikator derivatif = NA; banner di UI.
- **Jam pasar Gold:** walau kontrak perpetual diperdagangkan 24/7, pasar emas fisik tutup akhir pekan. Simpan kalender sesi (`core/time.py`): FX close Jumat 21:00 UTC → Minggu 22:00 UTC (+ penyesuaian DST AS). Di luar sesi: analisis tetap tampil, sinyal Gold diblok (macro filter M4).

### 5.2 Analisis & sinyal (`engine`)
Lihat `SIGNAL_ENGINE.md`. Kontrak:
```python
class IndicatorResult(BaseModel):
    key: str
    category: Literal["trend","momentum","order_flow","derivatives","microstructure","ml","sentiment"]
    state: Literal["BULL","BEAR","NEUTRAL","NA"]
    strength: float            # 0..1
    values: dict[str, float]
    reason: str                # 1 kalimat Bahasa Indonesia
    live_only: bool = False

class Analysis(BaseModel):
    symbol: str; tf: str; bar_time: datetime
    source: str                # "binance_futures:XAUUSDT"
    indicators: list[IndicatorResult]
    score: float               # -100..+100
    counts: dict[str, int]
    category_votes: dict[str, str]
    htf: dict[str, str]        # {"H1":"BULL","H4":"BULL","D1":"NEUTRAL"}
    macro: MacroFilterResult
    verdict: Literal["STRONG_LONG","LONG","NEUTRAL","SHORT","STRONG_SHORT"]
    strategy_b: StrategyBResult
    weights_version: str
```

### 5.3 Trade Ticket (resume siap eksekusi) — fitur inti baru
Setiap sinyal `STRONG_*` menghasilkan ticket:

```
🟢 BUY XAUUSD · M15 · Konfluensi-10 · skor 62
Berlaku s/d 08:45 WIB (3 bar) · Sumber harga: Binance XAUUSDT
Entry   : 2.651,0  (zona 2.649,5 – 2.652,0)     ← market bila harga di zona
SL      : 2.636,5  (−14,5 · 1,5×ATR)
TP1     : 2.665,5  (+1R, tutup 50%, SL → BE)
TP2     : 2.680,0  (+2R)
Lot     : 0,06 lot (risiko 1% dari $10.000 = $100 → aktual $87)  ← kalkulator broker
Invalidasi: close M15 di bawah 2.640,0 (Supertrend)
Alasan  : EMA ribbon & Supertrend bullish H1/M15 · CVD naik · di atas VWAP
Risiko  : CPI USD 19:30 WIB besok · RSI dekat overbought
```
- **Jarak relatif** (poin & ATR) selalu ditampilkan → bisa dipakai di broker mana pun walau harganya sedikit berbeda.
- **Kalibrasi harga broker:** user memasukkan harga broker saat ini (UI atau `/kalibrasi XAUUSD 2652.3` di Telegram) → offset = broker − sumber, berlaku 30 menit → semua level ticket digeser dan diberi label "disesuaikan untuk broker (+1,3)".
- **Kalkulator lot** per profil broker (`settings.brokers`): contract size (Gold 100 oz/lot di Exness; crypto CFD 1 unit/lot), min lot, step lot, mata uang akun, saldo, risiko %. Rumus Gold: `lot = risiko_usd / (jarak_SL_usd × contract_size)`, dibulatkan **ke bawah** ke step lot. Bila lot minimum sudah melebihi risiko yang diizinkan → tampilkan peringatan merah "Risiko aktual X% > batas", jangan diam-diam membulatkan ke atas.
- **Kedaluwarsa:** ticket expired setelah `ticket_valid_bars` (default 3) atau bila harga keluar zona > 0,5·ATR.
- **Status ticket:** `new → executed (isi harga fill & lot aktual) → closed (isi exit)` atau `skipped/expired`. Ini membentuk **Jurnal Eksekusi Nyata**, terpisah dari paper trading, sehingga user bisa membandingkan *paper vs real*.
- Tombol "Salin" (format teks di atas) dan "Salin ringkas" (satu baris: `BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.07lot`).

### 5.4 Market Brief (resume harian)
Dibuat `scheduler` 06:45 WIB (dan on-demand): untuk tiap simbol → bias H4/D1, skor M15 terakhir, level kunci (VWAP kemarin, high/low harian, swing H4, Supertrend H1), berita high-impact hari ini, ticket aktif, statistik 7 hari. Gemini menulis narasi ≤ 200 kata per simbol + ringkasan umum. Dikirim ke Telegram dan tampil di halaman **Brief**. Versi siang (13:45 WIB, sebelum sesi London) opsional.

### 5.5 Paper trading & risk
- Membuka posisi simulasi otomatis untuk setiap ticket. Entry di open bar berikutnya + slippage; biaya taker 0,05% per sisi (configurable).
- TP1 1R tutup 50% & SL ke BE; TP2 2R; exit bila sinyal berlawanan `STRONG`; time-stop 32 bar.
- Saldo virtual 1.000 USD, risiko 1%, maks 1 posisi/simbol, 3 total, daily loss limit 3% (pause sampai 00:00 WIB).
- SL & TP tersentuh di candle yang sama → SL dulu, kecuali data M1 tersedia untuk resolusi (backfill M1 on-demand dari Binance).

### 5.6 Komentar AI (`worker`)
- Dipicu: sinyal STRONG (otomatis), tombol UI / `/analisa` (on-demand), Market Brief.
- Input JSON terstruktur (Analysis + ticket + berita 24 jam + statistik setup serupa 30 hari). Tidak mengirim data akun/saldo.
- Output skema `AIComment` (lihat `SIGNAL_ENGINE.md` §8). Validasi angka; gagal → template.
- Rate limiter token-bucket di Redis (RPM/RPD dari `.env`), cache per `(symbol, tf, bar_time, kind)`, antrean arq, retry 429/5xx.
- Provider: `GeminiProvider` (default), `ClaudeProvider`, `TemplateProvider`. Kuota dipakai/sisa tampil di halaman Status.

### 5.7 Kalender berita
ForexFactory JSON mingguan (tanpa key) → fallback Finnhub. Refresh per jam, normalisasi UTC, blackout USD High ±30 mnt untuk semua simbol, alert Telegram 15 mnt sebelumnya.

### 5.8 Telegram (dua arah)
Long polling, whitelist `TELEGRAM_ALLOWED_CHAT_IDS`.

| Perintah | Fungsi |
|---|---|
| `/start` | Sapaan + chat_id + disclaimer |
| `/brief` | Market Brief terbaru |
| `/analisa <SIMBOL> [m15\|h1\|h4]` | Analisis + chart + komentar AI |
| `/ticket` | Ticket aktif |
| `/kalibrasi <SIMBOL> <harga_broker>` | Set offset harga broker |
| `/eksekusi <id> <harga> <lot>` · `/tutup <id> <harga>` | Catat eksekusi nyata |
| `/posisi` | Posisi paper terbuka |
| `/winrate [7d\|30d\|all] [paper\|real]` | Statistik |
| `/kalender` | Berita high-impact 48 jam |
| `/pause` · `/resume` · `/help` | |

Pesan ticket punya tombol inline **[✅ Saya eksekusi] [⏭ Lewati] [📊 Detail]**; "Saya eksekusi" meminta harga fill (reply) lalu mencatat ke Jurnal Eksekusi Nyata.

### 5.9 Jurnal & statistik
Dua buku: **Paper** (otomatis) dan **Real** (dari ticket yang dieksekusi user). Metrik: winrate, profit factor, expectancy (R), avg win/loss R, max drawdown, streak, jumlah trade; breakdown per simbol, strategi, sesi, verdict, hari, jam. **Akurasi per indikator**, **analisis sinyal terblokir** (simulasi virtual), **slippage nyata** (fill real vs entry ticket). Ekspor CSV.

### 5.10 Backtest & ML
- Data: Binance klines (paginasi 1500, cache di DB). Histori `XAUUSDT` baru sejak Jan 2026 → untuk Gold yang lebih panjang, loader opsional **Dukascopy XAU/USD** (data historis gratis) dengan label sumber berbeda.
- Runner event-driven memakai fungsi engine yang sama, dijalankan sebagai job `worker`, progress via WS.
- Laporan: metrik, equity, trade list, A vs B vs buy&hold, catatan indikator NA.
- LightGBM per simbol (detail `SIGNAL_ENGINE.md` §3.9), walk-forward dengan purge, aktif bila AUC OOS ≥ 0,55.

### 5.11 Auth & keamanan
- Satu admin. Dibuat oleh `migrate` dari `ADMIN_EMAIL`/`ADMIN_PASSWORD` di `.env` pada start pertama (password wajib ≥ 12 karakter); setelah itu ganti dari UI.
- Login → JWT akses 15 mnt + refresh 7 hari di cookie `httpOnly; SameSite=Strict` (`Secure` saat HTTPS); CSRF token double-submit untuk method non-GET; WS diautentikasi via cookie.
- Rate-limit login (5/menit/IP, lockout 15 mnt), argon2id, 2FA TOTP opsional, audit log (login, ubah setelan).
- Port hanya `127.0.0.1:8080` di host. Header keamanan via Caddy (CSP ketat, HSTS saat HTTPS, X-Frame-Options).
- Secret hanya di `.env`; log menyamarkan token/key.

### 5.12 Observability & operasional
- Log JSON `structlog` → `docker compose logs`; `logs.bat` menampilkan log ringkas.
- `/api/health` (liveness) & `/api/health/full` (Binance WS, lag stream, DB, Redis, AI kuota, Telegram, berita).
- `/metrics` Prometheus: lag ingest, durasi analisis, jumlah sinyal, error API eksternal, kuota AI.
- Halaman **Status** di UI menampilkan semua ini secara manusiawi.
- Backup: `scheduler` menjalankan `pg_dump` harian ke `./backups` (retensi 14 hari) + tombol restore terpandu di dokumen.

---

## 6. Halaman UI
Spesifikasi lengkap di `UI_SPEC.md`: Login · Dashboard · Brief · Analisa · Ticket & Sinyal · Posisi Paper · Jurnal (Paper/Real) · Backtest · Kalender · Status · Pengaturan.

## 7. Jalur ke VPS
Stack yang sama (`compose.yaml`) dijalankan di VPS Linux; tambahkan domain di Caddy untuk HTTPS otomatis, set `COOKIE_SECURE=true`, `PUBLIC_URL`. Tidak ada komponen Windows-only.

## 8. Disclaimer
Footer & `/start`: *"TradeRadar adalah alat bantu analisis, bukan nasihat keuangan. Harga sumber data dapat berbeda dari broker Anda — selalu cek ulang sebelum eksekusi. Winrate historis tidak menjamin hasil di masa depan."*
