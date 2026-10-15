# Changelog

Semua perubahan penting pada TradeRadar didokumentasikan di file ini.
Format mengikuti panduan [Keep a Changelog](https://keepachangelog.com/id/1.0.0/).

## [Fase 7: Telegram Dua Arah] - 2026-10-15

### Ditambahkan
- **TradeRadar Telegram Bot Engine (`traderadar.telegram`):**
  - **Arsitektur Long Polling & Lifespan Service (`bot.py`, `services/telegram.py`):** Integrasi `python-telegram-bot` v21.11 async tanpa dependency webhook/ngrok, berjalan mandiri dan tangguh di container Docker.
  - **Keamanan Whitelist Berlapis (`whitelist.py`):** Pembatasan akses berbasis `TELEGRAM_ALLOWED_CHAT_IDS`. Chat ID tidak terdaftar otomatis diabaikan tanpa memproses perintah atau membocorkan data. Persistensi status pendaftaran dan preferensi jeda notifikasi (`is_paused`) di tabel database `telegram_chats`.
  - **Suite Perintah Lengkap Bahasa Indonesia (`handlers.py`):**
    - `/start`: Sambutan, Chat ID unik, verifikasi whitelist, dan *financial disclaimer* wajib.
    - `/help`: Panduan ringkas daftar perintah trading dan eksekusi.
    - `/analisa <SIMBOL> [TF]`: Analisis konfluensi multi-indikator real-time dengan chart candlestick resolusi tinggi dan ulasan AI kontekstual (<= 20 detik).
    - `/ticket`: Daftar Trade Ticket aktif yang siap dieksekusi manual.
    - `/kalibrasi <SIMBOL> <HARGA>`: Kalibrasi offset harga broker pengguna (berlaku 4 jam).
    - `/eksekusi <id> <harga> <lot>`: Pencatatan eksekusi manual langsung ke Jurnal Real.
    - `/tutup <id> <harga>`: Penutupan trade real dengan kalkulasi otomatis PnL USD dan R-multiple.
    - `/posisi`: Pemantauan posisi terbuka Paper Trading secara live.
    - `/winrate [7d|30d|all] [paper|real]`: Metrik performa winrate, profit factor, dan expectancy.
    - `/kalender`: Agenda berita ekonomi High-Impact 48 jam ke depan.
    - `/pause` & `/resume`: Penyetelan jeda/aktif notifikasi per pengguna.
- **Headless Candlestick Chart PNG Generator (`charts.py`):**
  - Rendering grafik candlestick gelap (`#0B0E14`) menggunakan `mplfinance` dan `matplotlib` (backend `Agg`) berkecepatan tinggi (<= 300 ms).
  - Overlay Triple EMA (8, 21, 55), panel volume, dan level garis horizontal berwarna untuk Entry, SL, TP1, dan TP2.
- **Rich Ticket Broadcast & Alur Eksekusi Interaktif (`notifier.py`):**
  - Dispatcher tiket baru menunggu hingga 20 detik untuk ulasan AI agar terkirim dalam satu pesan terpadu.
  - Tiket disiarkan dengan grafik PNG, teks caption Markdown terstruktur, dan inline keyboard: `[✅ Saya eksekusi]`, `[⏭ Lewati]`, `[📊 Detail]`.
  - Alur "Saya eksekusi" interaktif 2 tahap menggunakan status pending di Redis (`tg:pending_exec:{chat_id}`), mencatat harga fill & lot ke `real_executions` dengan `source="telegram"`.
- **Sistem Notifikasi Proaktif Background:**
  - Siaran real-time exit posisi paper trading (TP1 hit, TP2 hit, SL hit, time stop).
  - Notifikasi pembatalan/tiket kedaluwarsa setelah batas waktu validasi habis.
  - Broadcast Market Brief harian otomatis setiap 06:45 WIB.
  - Rekap Kinerja Harian otomatis setiap 22:00 WIB (ringkasan paper trade & real trade hari ini).
  - Peringatan sistem saat koneksi data feed degraded atau recovered.
- **Settings & Telegram Diagnostics API (`routers/settings.py`):**
  - `GET /api/settings`: Konfigurasi umum aplikasi.
  - `GET /api/settings/telegram/status`: Status bot, konfigurasi token, jumlah pelanggan aktif, dan whitelist.
  - `POST /api/settings/telegram/test`: Pengujian pengiriman pesan diagnostik ke seluruh subscriber Telegram.
- **Pengujian & Verifikasi Kualitas:**
  - 31 unit test khusus modul Telegram (whitelist, message formatters, charts, handlers, notifier, settings API) lulus 100%.
  - Total 149 pengujian backend (`pytest`) lulus 100%.
  - Pengecekan linter Ruff lulus (`All checks passed!`).
  - Pengecekan mypy strict lulus (`Success: no issues found in 87 source files`).

## [Fase 6: Komentar AI & Market Brief] - 2026-10-15

### Ditambahkan
- **Sistem Provider Komentar AI Multi-Model (`traderadar.ai`):**
  - **Google Gemini Provider (`gemini.py`):** Integrasi langsung ke REST API Google Generative Language menggunakan model `gemini-2.5-flash` dengan `response_mime_type: "application/json"` dan skema terstruktur `response_schema` (Pydantic model `AIComment`). Dilengkapi penanganan retry exponential backoff dan fallback model otomatis.
  - **Template Provider Offline/Aturan (`template.py`):** Provider cadangan berbasis aturan deterministik dalam Bahasa Indonesia yang fasih. Aktif otomatis tanpa API key (zero-config out-of-the-box), saat kuota habis, saat terjadi kendala jaringan, atau ketika output AI terdeteksi mengandung halusinasi harga.
  - **Claude Provider Opsional (`claude.py`):** Dukungan opsional provider Anthropic Claude (`claude-3-5-sonnet-20241022`) via Messages API tool-use structured output.
  - **AI Service Orchestrator (`service.py`):** Orkestrasi bertahap: Cek cache Redis $\rightarrow$ Rate limiter $\rightarrow$ Eksekusi provider primer $\rightarrow$ Validasi angka anti-halusinasi $\rightarrow$ Fallback otomatis ke Template jika gagal/invalid $\rightarrow$ Persistensi database PostgreSQL $\rightarrow$ Publikasi event Redis UI Pub/Sub.
- **Validasi Anti-Halusinasi & Kebenaran Angka Ketat (`validate.py`):**
  - Pemeriksaan batas panjang ringkasan naratif ($\le 120$ kata) tanpa janji keuntungan/profit.
  - Verifikasi matematis ketat pada setiap angka desimal (`level_penting`): setiap level harga harus bersumber dari data input teknikal aktual (entry, SL, TP1, TP2, VWAP, EMA, Bollinger, Supertrend, High/Low, OBI) dengan toleransi ketat $\pm 0.8\%$ atau $\le 0.5$ poin absolut.
  - Kegagalan validasi langsung mengesampingkan output LLM dan mengalihkan ke Template Engine dengan badge `is_fallback = True`.
- **Redis Token-Bucket Rate Limiter (`ratelimit.py`):**
  - Pembatasan 5 RPM (Requests Per Minute) sliding window.
  - Pembatasan 100 RPD (Requests Per Day) sliding counter (reset otomatis tiap pukul 00:00 WIB).
  - Monitoring statistik kuota aktif real-time melalui endpoint `GET /api/ai/quota` dan `FullHealthResponse` (`/api/health/full`).
- **Market Brief Generator & Penjadwal Rutin (`brief.py`, `scheduler.py`, `worker.py`):**
  - Kompilasi snapshot teknikal multi-aset (XAUUSDT, BTCUSDT, ETHUSDT, SOLUSDT) mencakup VWAP kemarin, rentang harian (daily high/low), dan skor konfluensi.
  - Scheduler cron mengeksekusi pembuatan Market Brief pagi otomatis setiap pukul 06:45 WIB (`brief_morning`).
  - Worker arq mengonsumsi stream Redis `signals.stream` dan secara otomatis memicu ulasan AI saat terdeteksi sinyal kuat (`STRONG_LONG` atau `STRONG_SHORT`).
- **Database Schema & Migrasi PostgreSQL:**
  - Migrasi Alembic `005_create_phase6_tables.py` untuk tabel `market_briefs` dan `ai_comments`.
  - SQLAlchemy models `MarketBriefRecord` dan `AICommentRecord` di `traderadar.core.models`.
- **REST API Endpoints:**
  - `GET /api/analysis/{symbol}/ai`: Mengambil komentar AI tersimpan terbaru untuk simbol dan timeframe terkait.
  - `POST /api/analysis/{symbol}/ai`: Meminta analisis AI on-demand untuk simbol dan timeframe aktif.
  - `GET /api/briefs/latest`: Mengambil Market Brief terbaru (edisi pagi / siang).
  - `POST /api/briefs`: Memperbarui atau membuat Market Brief baru secara on-demand.
  - `GET /api/ai/quota`: Mendapatkan informasi kuota RPM dan RPD terkini beserta provider aktif.
- **Frontend Professional UI (`frontend/`):**
  - **Panel Tanggapan AI (`AICommentPanel.tsx`):**
    - Terintegrasi pada Kolom Keputusan `AnalisaPage.tsx`.
    - Badge model aktif (`Gemini 2.5 Flash` / `Komentar Otomatis (Template)`), status sisa kuota, dan tombol permintaan analisis.
    - Bias badge interaktif (`BULLISH`, `BEARISH`, `NETRAL`), keyakinan (`Tinggi`, `Sedang`, `Rendah`), serta indikator kesepakatan engine vs AI.
    - Ringkasan naratif, perbandingan skenario bullish vs bearish, kartu alasan utama & faktor risiko, chip level penting terverifikasi, serta kondisi invalidasi tesis & rekomendasi manajemen risiko.
    - Metrik latensi generasi, timestamp WIB, dan token usage.
  - **Halaman Market Brief (`BriefPage.tsx` di `/brief`):**
    - Ringkasan pasar harian dengan badge sentimen makro (`Risk-on`, `Risk-off`, `Netral`).
    - Tabel level kunci multi-aset (XAUUSDT, BTCUSDT, ETHUSDT, SOLUSDT): harga terakhir, VWAP kemarin, high kemarin, low kemarin, dan skor konfluensi.
    - Kartu narasi terpadu per aset dengan skenario pergerakan hari ini dan level pivot.
    - Tombol aksi: "Buat Ulang Brief" (on-demand), "Salin Teks" markdown, dan integrasi notifikasi bot Telegram.
    - Terintegrasi penuh ke navigasi bilah sisi (`Sidebar.tsx`) dan routing `Shell.tsx`.
  - **Monitoring Status Sistem (`StatusPage.tsx`):**
    - Kartu pemantauan kuota AI real-time dengan progress bar persentase penggunaan RPD, indikator RPM aktif, serta identifikasi model aktif.
  - **Palet Perintah (`CommandPalette.tsx`):**
    - Aksi cepat "Buka Market Brief Harian AI" dan "Buat Market Brief Baru (On-demand)".
- **Pengujian & Verifikasi Kualitas:**
  - 118 pengujian unit backend (`pytest`) lulus 100% (termasuk validasi angka karangan, template provider, gemini mock, rate limiter, API endpoints).
  - 14 pengujian unit frontend (`vitest`) lulus 100% (`AICommentPanel.test.tsx`, `BriefPage.test.tsx`, dll.).
  - Pengecekan linter Ruff dan MyPy Strict lulus tanpa error pada seluruh source code backend.
  - Pengecekan linter ESLint lulus dengan 0 warning dan 0 error pada frontend.
  - Build produksi bundle Vite frontend sukses tanpa error.

## [Fase 5: Trade Ticket, Kalibrasi Broker, Paper Trading] - 2026-10-15

### Ditambahkan
- **Trade Ticket Generator & Risk Engine (`traderadar.engine.risk`, `traderadar.engine.ticket`):**
  - Kalkulator ukuran lot deterministik berbasis alokasi risiko saldo akun (default 1% risiko dari $10.000 saldo), ukuran kontrak instrumen (mis. 100 oz untuk XAUUSD CFD), dan pembulatan ke bawah sesuai kelipatan step lot broker (`floor_to_step`).
  - Reproduksi presisi contoh `BLUEPRINT.md` §5.3 terverifikasi oleh test: Entry 2651.0, SL 2636.5 (1.5×ATR), TP1 2665.5 (1.0R), TP2 2680.0 (2.0R), ukuran 0.06 lot untuk saldo $10.000, risiko aktual $87.0 (0.87%).
  - Peringatan batas lot minimum (`min_lot_warning`) otomatis jika risiko pada 1 lot minimum broker melampaui toleransi risiko yang ditetapkan.
  - Zona toleransi entry relatif ATR ($\pm 0.1 \times \text{ATR}$), evaluasi kedaluwarsa deterministik:
    - `EXPIRED_TIME`: kedaluwarsa setelah 3 bar candle close (45 menit pada M15).
    - `CHASE_LIMIT`: pembatalan tiket jika harga live melesat searah target $> 0.5 \times \text{ATR}$ sebelum sempat terisi.
    - `SL_HIT_BEFORE_ENTRY`: pembatalan tiket jika harga pasar menyentuh SL sebelum menyentuh zona entry.
  - Generator teks Bahasa Indonesia terstruktur:
    - Format ringkas: `BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot`.
    - Format lengkap: detail zona entry, level SL/TP, invalidasi, alasan konfluensi, dan checklist risiko makro.
- **Kalibrasi Broker CFD & Futures (`traderadar.services.ticket_store`, `broker_calibrations`):**
  - Mekanisme kalibrasi harga offset ($\Delta = P_{\text{broker}} - P_{\text{source}}$) dengan masa berlaku 4 jam.
  - Penyesuaian otomatis seluruh level tiket (Entry, SL, TP) saat offset aktif, menyajikan perbandingan harga Sumber vs Broker vs Jarak Relatif di kartu tiket UI.
- **Paper Trading Engine Lengkap (`traderadar.engine.paper`, `traderadar.services.paper_store`):**
  - Eksekusi fill posisi pada Open candle bar berikutnya dengan slippage taker 2 bps (0.02%) dan fee taker 0.05%.
  - Konservatisme bar: prioritas evaluasi Stop Loss jika candle menyentuh level SL dan TP dalam bar yang sama.
  - Aturan Partial TP: TP1 menutup 50% posisi dan memindahkan SL ke Breakeven (BE); TP2 menutup sisa 50% posisi.
  - Time Stop otomatis: posisi ditutup pada harga candle close setelah berjalan $\ge 32$ bar (8 jam pada M15).
  - Opposite Exit: posisi ditutup segera bila muncul sinyal kuat berlawanan arah.
  - Batas Kerugian Harian (Daily Loss Limit): penghentian order paper baru jika akumulasi kerugian hari ini mencapai $\ge 3\%$ dari modal awal ($1.000).
  - Simulasi Virtual Sinyal Terblokir: sinyal yang dibatalkan oleh Macro Filter tetap disimulasikan (`is_virtual=True`) untuk evaluasi akurasi filter makro.
- **Jurnal Eksekusi Nyata (`real_executions`):**
  - Pencatatan eksekusi nyata dari pengguna (Fill price, lot, waktu, catatan) tanpa pernah memanggil endpoint eksekusi broker/exchange (read-only compliance).
  - Kalkulasi otomatis slippage nyata terhadap harga referensi sinyal.
- **Database & Model Penyimpanan:**
  - Migrasi Alembic `004_create_phase5_tables.py` untuk tabel `tickets`, `broker_calibrations`, `paper_trades`, dan `real_executions`.
  - SQLAlchemy models di `traderadar.core.models`.
- **Integrasi Service Engine (`traderadar.services.engine`):**
  - Pembentukan ticket otomatis saat sinyal `STRONG` terkonfirmasi lolos filter makro.
  - Pembukaan posisi paper trade dan pembaruan berkala status posisi pada setiap event candle close M15.
- **REST API Endpoints:**
  - `/api/tickets`: daftar tiket dengan filter simbol dan status, detail tiket dengan kalibrasi broker.
  - `/api/tickets/{id}/execute`, `/close`, `/skip`: manajemen eksekusi nyata dan pembatalan tiket.
  - `/api/calibrations`, `/api/calibrations/active`: manajemen kalibrasi offset broker.
  - `/api/paper/trades`, `/api/paper/metrics`, `/api/paper/trades/{id}/close`: pemantauan performa dan manajemen posisi paper trading.
- **Frontend Professional UI (`frontend/`):**
  - **Halaman Tiket & Sinyal (`TicketPage.tsx`):**
    - Tab navigasi Aktif, Riwayat, dan Terblokir dengan filter simbol.
    - Kartu tiket interaktif (`TicketCard.tsx`) dengan live countdown timer, tabel perbandingan level harga, kalkulator lot kustom, tombol salin ringkas & lengkap, serta dialog kalibrasi broker, eksekusi nyata, dan tutup posisi.
  - **Halaman Paper Trading (`PaperPage.tsx`):**
    - Kartu KPI performa (`PaperAccountCard.tsx`): Equity, PnL Harian, Winrate %, Posisi Terbuka, dan indikator batas kerugian harian.
    - Tabel posisi paper lengkap (`PaperTradesTable.tsx`) dengan filter tab (Semua, Terbuka, Riwayat, Simulasi Virtual), badge alasan exit (TP1, TP2, BE, SL, Time Stop, Opposite Signal, Manual), dan modal penutupan manual.
  - **Integrasi Analisa & Cockpit:**
    - `AnalisaPage.tsx`: integrasi kartu tiket aktif langsung pada kolom keputusan.
    - `DashboardPage.tsx`: seksi khusus tiket sinyal aktif siap eksekusi di cockpit utama.
    - `Shell.tsx`: integrasi tab menu navigasi `Ticket` dan `Paper`.
- **Pengujian & Verifikasi Kualitas:**
  - 107 pengujian unit backend (`test_ticket.py`, `test_paper_trader.py`, `test_ticket_and_paper_api.py`, dll.) lulus 100%.
  - 10 pengujian vitest frontend lulus 100%.
  - Linter Ruff dan Mypy Strict lulus tanpa error pada seluruh source code.
  - Build produksi Vite frontend sukses (489 kB bundle, 0 error).

## [Fase 4: Skor, Macro Filter, Strategi B, Panel Analisa] - 2026-10-15

### Ditambahkan
- **Engine Skor Konfluensi & Voting Kategori (`traderadar.engine.scoring`):**
  - Implementasi perhitungan skor konfluensi ternormalisasi (-100 s/d +100) sesuai formula `SIGNAL_ENGINE.md` §4:
    - Normalisasi bobot dinamis: indikator `NA` dibuang dari pembilang dan penyebut.
    - Suara kategori (Trend, Momentum, Order Flow, Derivatif, Mikrostruktur, ML, Sentimen) dihitung bertanda (`w * s * strength`).
    - Evaluasi konfirmasi H1 berbasis mayoritas dari EMA Ribbon H1, Supertrend H1, dan posisi RSI H1 terhadap level 50.
    - Penentuan verdict deterministik (`STRONG_LONG`, `LONG`, `NEUTRAL`, `SHORT`, `STRONG_SHORT`):
      - `STRONG_LONG`: Skor ≥ 55, ≥ 3 kategori BULL, kategori Trend = BULL, konfirmasi H1 bukan BEAR, Macro Filter PASS, dan bobot tersedia ≥ 50%.
      - Batas bobot: bila total bobot tersedia < 50%, verdict dibatasi ke pantau (`LONG`/`SHORT`) dan tidak boleh `STRONG`.
- **Macro Filter Gerbang M1–M8 (`traderadar.engine.macro_filter`):**
  - Evaluasi 8 gerbang makro independen yang mengembalikan detail alasan dalam Bahasa Indonesia:
    - **M1 (Tren Besar HTF):** H4 close vs EMA200 H4 dan Supertrend D1; gagal hanya bila KEDUA-DUANYA berlawanan dengan arah sinyal.
    - **M2 (Berita High-Impact):** Jendela blackout USD High-impact (±30 menit).
    - **M3 (Volatilitas ATR):** Evaluasi ATR14 M15 terhadap persentil 30 hari (P10 s/d P95) untuk mendeteksi pasar mati (< P10) atau volatilitas ekstrem (> P95).
    - **M4 (Sesi Pasar Gold):** Kalender sesi TradFi emas (`core.time` dengan penyesuaian DST AS) mendeteksi pasar tutup akhir pekan dan jendela rollover harian spread broker (20:45–01:15 UTC).
    - **M5 (Likuiditas Spread):** Spread best bid/ask orderbook vs 2× median 24 jam.
    - **M6 (Kesegaran Data):** Keterlambatan candle > 2× TF, status WebSocket putus, atau warmup sumber fallback Gold < 60 menit.
    - **M7 (Funding Ekstrem):** |funding rate| > 0.1% per 8 jam.
    - **M8 (Batas Risiko Paper):** Daily loss limit paper trade (3%) dan pembatasan posisi aktif per simbol.
- **Strategi B: Triple-EMA (`traderadar.engine.strategies.triple_ema`):**
  - EMA cepat 9 (close), EMA tengah 21 (applied to Open), EMA lambat 50 (close).
  - Crossover M15 dengan konfirmasi slope 5-bar EMA50 dan susunan EMA H1.
  - Perhitungan level SL dinamis (swing low/high 10 bar vs 1.2×ATR, diapit minimal 0.8×ATR) dan target TP 1R.
  - Evaluasi gerbang Macro Filter M2–M6.
- **Pipeline Koordinasi Strategi A & B (`traderadar.engine.strategies.konfluensi10`):**
  - Eksekusi terpadu 10 indikator M15, multi-timeframe bias (H1, H4, D1), Macro Filter M1-M8, serta mekanisme cooldown 4 bar untuk sinyal searah pada simbol yang sama.
- **Database & Model Penyimpanan (`analyses` & `signals`):**
  - Migrasi Alembic `003_create_analyses_and_signals_tables.py` untuk tabel `analyses` (dengan constraint unik per `symbol, tf, bar_time`) dan `signals` (termasuk sinyal terblokir dengan array `blocked_by`).
  - SQLAlchemy models `AnalysisRecord` dan `SignalRecord` di `traderadar.core.models`.
  - Repository `traderadar.services.analysis_store` dengan fungsi upsert idempotensial dan kueri riwayat.
- **Background Service Engine (`traderadar.services.engine`):**
  - Konsumsi event Redis Stream `candles.closed` dalam consumer group `engine`.
  - Publikasi real-time ke PubSub `ui.events` (event `analysis` dan `signal`) untuk pembaruan instan di WebSocket clients (< 2 detik).
  - Emisi sinyal terkonfirmasi ke stream Redis `signals`.
- **REST API Endpoints:**
  - `GET /api/analysis/{symbol}?tf=M15&preview_live=false`: menyajikan analisis lengkap closed bar atau preview bar berjalan.
  - `GET /api/analysis/{symbol}/history?tf=M15&limit=48`: data timeseries riwayat skor 48 jam.
  - `GET /api/signals?symbol=&strategy=&status=&limit=50`: daftar sinyal terverifikasi maupun terblokir.
- **Frontend Professional UI (`frontend/`):**
  - **Analisa Page (`AnalisaPage.tsx`):**
    - Layout 3-kolom trading terminal modern:
      1. Kolom Chart: candlestick + volume, overlay toggles, marker sinyal historis (▲/▼ berwarna), pane RSI & CVD, dan mini area chart riwayat skor 48 jam (`ScoreHistoryChart.tsx`).
      2. Kolom Indikator: ringkasan konfluensi, widget `ScoreGauge.tsx` dengan indikator linear visual dan chip hitungan `▲ • ▼`, serta 10 kartu indikator dikelompokkan per kategori.
      3. Kolom Keputusan: checklist `MacroChecklist.tsx` (M1–M8 dengan badge lolos/gagal), widget bias HTF (H1, H4, D1), panel `StrategyBPanel.tsx`, teaser Trade Ticket, dan AI Brief.
  - **Dashboard Page (`DashboardPage.tsx`):**
    - Kartu watchlist lengkap diperkaya dengan gauge skor M15, ringkasan suara indikator, badge status macro filter (`✓ Macro` / `⚠ Terblokir`), dan bias HTF multi-timeframe.
  - Regenerasi TypeScript types via OpenAPI `npm run gen:api` (zero `any`).
- **Pengujian & Verifikasi Kualitas:**
  - 91 pengujian unit backend lulus 100% (scoring, macro filter M1-M8, Strategy B, pipeline konfluensi, API endpoints).
  - Frontend Vitest (ScoreGauge, MacroChecklist, App Shell) lulus 100%.
  - Mypy Strict dan Ruff linter lulus tanpa error.
  - Production build Vite lulus tanpa error (3.02s).

## [Fase 3: 10 Indikator] - 2026-10-15

### Ditambahkan
- **Engine Indikator Deterministik (`traderadar.engine.indicators`):**
  - Implementasi 10 indikator teknikal sesuai spesifikasi `docs/SIGNAL_ENGINE.md` §3 dengan type hints penuh (`mypy --strict`) dan zero lookahead bias:
    1. **VWAP Session (`vwap.py`):** Reset harian 00:00 UTC, deviasi standar berbobot volume (±1σ, ±2σ), z-score jarak harga, slope regresi 4-bar, dan penalti mean-reversion bila overextended (|z| > 2).
    2. **EMA Ribbon (`ema_ribbon.py`):** 5 EMA (8, 13, 21, 34, 55), normalisasi jarak terhadap Wilder ATR 14, deteksi ribbon penuh vs parsial, serta deteksi counter-trend pullbacks.
    3. **Supertrend (`supertrend.py`):** Wilder ATR 10, multiplier 3.0, source (H+L)/2, pelacakan flip arah, dan penalti jarak sempit (< 0.3 ATR).
    4. **RSI (`rsi.py`):** Wilder RSI 14, deteksi pivot berkonfirmasi anti-lookahead (`left=5, right=3`, hanya dikenali pada candle t-3), divergensi reguler bull/bear, crossover level 50, dan deteksi overbought (>70) / oversold (<30).
    5. **Bollinger Bands (`bollinger.py`):** SMA 20, 2σ, %B, Bandwidth, deteksi squeeze persentil 20 (historis 120 bar), breakout pasca-squeeze, serta trend bounce di upper/lower band.
    6. **CVD / OBV (`cvd_obv.py`):** Akumulasi delta volume taker beli/jual kontinu, reset visual sesi harian 00:00 UTC, fallback ke OBV jika data taker volume tidak tersedia, slope regresi 20-bar dinormalisasi std 100-bar, dan deteksi divergensi/absorpsi volume.
    7. **Funding Rate & Open Interest Matrix (`funding_oi.py`):** Evaluasi 4 kuadran matriks perubahan harga 4-jam (ΔP%) vs open interest (ΔOI%), penalti crowded long funding rate (> +0.05%), dan bonus short squeeze funding negatif (< -0.03%).
    8. **Orderbook Imbalance (`orderbook.py`):** Analisis ketidakseimbangan bid/ask depth volume pada rentang ±0.5% dari mid price dengan flag `live_only=True` dan fallback gracefully jika offline.
    9. **LightGBM Directional Classifier Model (`lightgbm.py`):** Kompatibilitas model inference prediksi probabilitas arah triple-barrier (p_up, p_down) dengan margin threshold ≥ 0.15 dan probabilitas minimum ≥ 0.58, serta validasi metrik OOS AUC ≥ 0.55 sebelum aktif.
    10. **Sentiment Index (`sentiment.py`):** Agregasi Fear & Greed kontrarian (Crypto) dan rasio akun Long/Short (Crypto & Gold) dengan penalti crowded positioning.
  - Modul koordinasi `traderadar.engine.calculator.IndicatorEngine`: evaluasi vectorized seluruh 10 indikator secara terintegrasi dengan waktu eksekusi ~2–5 ms per 1.000 candle (jauh di bawah batas toleransi SLA < 300 ms).
  - Serializer timeseries overlay chart (VWAP bands, EMA Ribbon, Supertrend, Bollinger Bands) dan sub-panes (RSI, CVD) untuk konsumsi frontend.
- **Validasi Paritas TradingView & Anti-Lookahead:**
  - Fixture candle real dari Binance Futures: `ethusdt_m15_2000.csv` dan `xauusdt_m15_2000.csv` (2.000 candle M15).
  - Reference benchmark values `backend/tests/fixtures/reference_values.json` dari TradingView dengan toleransi perbedaan ≤ 0.1%.
  - Pengujian invarian anti-lookahead (`df[:t]` vs `df[:t+50]`): nilai indikator pada candle t terbukti 100% identik tanpa kebocoran data masa depan.
- **REST API Endpoint (`backend/src/traderadar/api/routers/market.py`):**
  - Endpoint `GET /api/indicators?symbol=...&tf=...&limit=...`: menyajikan hasil perhitungan terkini 10 indikator, skor per kategori (Trend, Momentum, Volume, Orderflow, Stat), status validitas, alasan dalam Bahasa Indonesia, serta payload timeseries multi-pane chart.
- **Frontend TradingView Multi-Series Overlay & Sub-Panes (`frontend/`):**
  - Multi-series overlays pada `TradingViewChart`:
    - Garis VWAP dan pita deviasi ±1σ, ±2σ.
    - EMA Ribbon 5 garis (8, 13, 21, 34, 55) dengan gradien warna biru-keunguan.
    - Supertrend line dengan pewarnaan dinamis bullish (hijau) / bearish (merah).
    - Bollinger Bands (Upper, Middle, Lower).
    - Tombol toggle interaktif untuk menampilkan/menyembunyikan masing-masing overlay.
  - Sub-panes tersinkronisasi:
    - RSI Pane: garis RSI dengan garis referensi overbought (70), midpoint (50), dan oversold (30).
    - CVD Pane: garis delta volume kumulatif dengan histogram delta per bar.
  - Kartu Analisis 10 Indikator di `AnalisaPage`:
    - Grid visual 10 indikator dengan badge status (BULLISH, BEARISH, NEUTRAL, SQUEEZE, CROWDED, OVERBOUGHT, OVERSOLD).
    - Visual bar kekuatan indikator (0–100%).
    - Tooltip deskripsi matematis & alasan kondisi sinyal dalam Bahasa Indonesia.
- **Pengujian & Metrik Kualitas:**
  - 70 pengujian unit & integrasi backend lulus 100% (26 tes indikator mendalam, tes paritas TradingView, tes anti-lookahead, tes performa benchmark).
  - Test coverage pada package `traderadar.engine.indicators` mencapai 100% (melampaui target minimum 85%).
  - Mypy Strict dan Ruff linter lulus tanpa peringatan atau error di seluruh 61 file backend.
  - Frontend TypeScript compiler dan ESLint lulus 100% tanpa error, zero `any`.

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
