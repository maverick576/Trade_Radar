# Roadmap Eksekusi — Fase & Acceptance Criteria

Kerjakan berurutan, satu fase per sesi/PR. Akhir setiap fase: `docker compose up -d --build` sukses dari nol, semua test & lint lulus, checklist dicentang, catatan di `docs/CHANGELOG.md`, keputusan di `docs/DECISIONS.md`.

Estimasi: ±14–18 sesi agent.

---

## Fase 0 — Fondasi, Docker, CI
- [x] Struktur repo (`BLUEPRINT.md` §4), `uv` project, Vite app, pre-commit (ruff, mypy, eslint, prettier).
- [x] `compose.yaml` + `compose.dev.yaml`, Dockerfile Python & web, Caddyfile, `init.sql` (timescaledb) — sesuai `INFRA_DOCKER.md`. Pin versi image.
- [x] `core/`: config (`.env` + `settings.yaml` tervalidasi Pydantic, error jelas bila salah), logging structlog, koneksi DB & Redis, skema event.
- [x] Service kerangka (api, ingestor, engine, worker, scheduler, telegram) hidup + heartbeat; `/api/health/full`.
- [x] Skrip `start.bat`, `stop.bat`, `logs.bat`, `update.bat`, `backup.bat`, `reset-data.bat`.
- [x] CI GitHub Actions.
- **Selesai bila:** di PC dengan Docker Desktop, dobel-klik `start.bat` → semua container `healthy` < 3 menit → browser terbuka ke halaman placeholder.

## Fase 1 — Auth & shell UI profesional
- [x] Tabel users/refresh_tokens/audit_log, `migrate` membuat admin dari `.env`.
- [x] Login/logout/refresh, CSRF, rate-limit login, ganti password, 2FA TOTP opsional.
- [x] Frontend: design system (`UI_SPEC.md` §1), shell (sidebar, topbar, command palette, tema), halaman Login, Status, route terlindungi, klien API hasil generate OpenAPI.
- **Selesai bila:** tanpa login semua `/api/*` (kecuali login/health) → 401; Playwright login lulus; Lighthouse Accessibility ≥ 95 di Login.

## Fase 2 — Data market real (Binance, Gold, fallback)
- [x] Verifikasi `XAUUSDT` di `exchangeInfo` + endpoint OI/LS/depth; tulis hasil ke `DECISIONS.md`.
- [x] `BinanceConnector` futures & spot: backfill, combined WS (kline, depth, markPrice), poll OI/LS/F&G, reconnect 23 jam, gap fill, throttle weight.
- [x] Rantai sumber Gold (XAUUSDT → PAXGUSDT → OANDA opsional) dengan switch otomatis + event status.
- [x] Kalender sesi pasar Gold (DST AS).
- [x] Hypertable candles/derivatives/sentiment + kompresi.
- [x] API `/symbols`, `/candles`; WS `tick`, `candle`; halaman Analisa: chart live + pilih TF; Dashboard: kartu harga live.
- **Selesai bila:** harga di UI cocok dengan Binance (≤ 0,05%); putus internet 2 menit → tersambung lagi tanpa candle bolong; memblokir XAUUSDT (simulasi di test) → otomatis PAXG + banner.

## Fase 3 — 10 indikator
- [x] `engine/indicators/*` sesuai `SIGNAL_ENGINE.md` §3, perhitungan inkremental.
- [x] Unit test nilai referensi TradingView & anti-lookahead.
- [x] Overlay chart & pane RSI/CVD.
- **Selesai bila:** coverage `engine/indicators` ≥ 85%, nilai cocok ≤ 0,1%, durasi analisis < 300 ms/simbol/TF.

## Fase 4 — Skor, macro filter, Strategi B, panel Analisa
- [x] `scoring`, `macro_filter` (M1–M8), `strategies/konfluensi10`, `strategies/triple_ema`, konsumsi `candles.closed`, preview live.
- [x] Simpan `analyses` & `signals` (termasuk terblokir).
- [x] UI Analisa lengkap (10 kartu indikator, gauge, macro checklist, Strategi B, marker sinyal, riwayat skor); kartu watchlist Dashboard lengkap.
- **Selesai bila:** setiap close M15, UI ter-update ≤ 2 dtk; test scoring/macro/sesi lulus.

## Fase 5 — Trade Ticket, kalibrasi broker, paper trading
- [x] `risk.py`, `ticket.py` (zona, jarak relatif, invalidasi, kedaluwarsa), profil broker & kalkulator lot, kalibrasi offset.
- [x] Paper trader (fill next open, biaya, TP1→BE→TP2, time stop, opposite exit, limit harian) + simulasi virtual sinyal terblokir.
- [x] Eksekusi nyata: execute/close/skip ticket → `real_executions`.
- [x] UI Ticket & Sinyal (kartu ticket, dialog kalibrasi/eksekusi/tutup, Salin lengkap/ringkas), Posisi Paper.
- **Selesai bila:** test ticket & paper lulus; contoh di `BLUEPRINT.md` §5.3 direproduksi persis oleh test (entry 2651, SL 2636,5, TP 2665,5/2680, 0,06 lot untuk $10.000).

## Fase 6 — Komentar AI & Market Brief
- [x] `ai/` provider Gemini (structured output) + template + Claude opsional; rate limit Redis; cache; validasi angka; job arq.
- [x] Market Brief pagi 06:45 WIB (+ siang opsional) via scheduler; halaman Brief.
- [x] Panel Tanggapan AI di Analisa; kuota di Status.
- **Selesai bila:** komentar ≤ 15 dtk; tanpa API key → template + badge; test angka karangan → fallback.

## Fase 7 — Telegram dua arah
- [x] Bot long polling + whitelist, semua perintah (`BLUEPRINT.md` §5.8), pesan ticket + chart PNG + tombol inline, alur "Saya eksekusi" (minta harga fill), `/kalibrasi`.
- [x] Notifikasi: ticket, TP/SL paper, ticket expired, status sistem, Brief, rekap 22:00 WIB.
- **Selesai bila:** `/analisa XAUUSD` membalas teks + gambar ≤ 20 dtk; eksekusi via Telegram muncul di Jurnal Real; chat tak terdaftar diabaikan.

## Fase 8 — Jurnal & statistik
- [ ] `stats/` + continuous aggregate; buku Paper/Real/Bandingkan, akurasi per indikator, nilai macro filter, slippage nyata, heatmap, ekspor CSV.
- **Selesai bila:** angka UI = skrip verifikasi SQL independen; `/winrate` Telegram konsisten dengan UI.

## Fase 9 — Kalender berita
- [ ] NewsService (ForexFactory + Finnhub), blackout M2, halaman Kalender, countdown topbar, alert 15 mnt, `/kalender`.
- **Selesai bila:** event High USD minggu ini tampil jam WIB benar; sinyal saat blackout `blocked_by` berisi M2.

## Fase 10 — Backtest
- [ ] Loader histori (Binance paginasi/bulk, Dukascopy opsional untuk Gold) dengan cache; runner event-driven (fungsi engine yang sama) sebagai job; laporan; halaman Backtest + bandingkan run.
- **Selesai bila:** backtest 6 bulan ETHUSDT M15 < 3 menit; deterministik; test paritas live vs backtest pada periode yang sama.

## Fase 11 — LightGBM & kalibrasi bobot
- [ ] Features, triple-barrier, walk-forward + purge, registry, aktivasi AUC ≥ 0,55, retrain mingguan, UI model; optimizer walk-forward opsional + peringatan overfitting.
- **Selesai bila:** model aktif ≥ 2 simbol dengan metrik OOS; test kebocoran fitur lulus.

## Fase 12 — Pengerasan & dokumentasi
- [ ] Pengaturan lengkap (hot reload setelan tanpa restart container), backup/restore teruji, profil `monitoring` (Prometheus + dashboard Grafana), uji ketahanan 72 jam (memori stabil, lag stream < 5 dtk), Playwright e2e penuh, `README.md` & `SETUP_WINDOWS.md` diperbarui sesuai kondisi akhir.

---

## Kriteria sukses produk (4–6 minggu pemakaian)
- ≥ 100 paper trade Strategi A dan ≥ 20 eksekusi nyata tercatat.
- Laporan winrate, expectancy, profit factor per simbol/strategi untuk Paper vs Real.
- Keputusan mempertahankan/mengubah macro filter & bobot berdasarkan data jurnal, versi bobot tercatat.
