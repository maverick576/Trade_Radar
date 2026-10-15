# AGENTS.md — Instruksi untuk Agent Eksekutor

> Dibaca pertama oleh agent coding (VSCode Copilot/Claude Code/Cursor/Antigravity).
> Proyek: **TradeRadar** — web app profesional untuk analisis market real-time (crypto + Gold, semua data dari web API),
> sinyal konfluensi multi-indikator, komentar AI (Gemini), **Trade Ticket** untuk eksekusi manual,
> paper trading, jurnal winrate (paper & real), backtest, kalender berita, dan bot Telegram dua arah.
> Berjalan di **Docker Desktop** (Windows/WSL2), siap pindah ke VPS.

## Urutan baca dokumen
1. `docs/BLUEPRINT.md` — produk, arsitektur service, stack, struktur repo, modul. **Wajib.**
2. `docs/SIGNAL_ENGINE.md` — indikator, skor, macro filter, risk, ticket, AI schema. **Sumber kebenaran logika trading.**
3. `docs/API_AND_DATA.md` — sumber data, skema Postgres/Timescale, event Redis, REST/WS.
4. `docs/UI_SPEC.md` — design system & spesifikasi halaman.
5. `docs/INFRA_DOCKER.md` — compose, Dockerfile, Caddy, skrip, CI.
6. `docs/ROADMAP.md` — fase & acceptance criteria. **Kerjakan berurutan.**
7. `docs/SETUP_WINDOWS.md` — panduan user. Jaga tetap akurat.
8. `config/settings.example.yaml`, `.env.example`.

## Aturan kerja
- **Satu fase per sesi/PR.** Di akhir fase: build dari nol (`docker compose build --no-cache` bila Dockerfile berubah), test & lint lulus, centang checklist, tulis `docs/CHANGELOG.md`.
- **Kualitas profesional:** type hints penuh (mypy strict untuk `engine/`, `core/`), TypeScript strict tanpa `any`, fungsi kecil & teruji, tidak ada kode mati/TODO tanpa issue. Conventional Commits.
- **Data harus real.** Tidak ada data dummy di UI. Mock hanya di test.
- **Tanpa MetaTrader / tanpa eksekusi order.** Jangan pernah memanggil endpoint order/akun exchange atau broker. Data hanya dari endpoint publik/market data.
- **Tidak ada repaint.** Sinyal hanya pada candle close; nilai live diberi label "LIVE · belum close".
- **Logika sinyal deterministik.** AI hanya menjelaskan/menanggapi; tidak memutuskan sinyal.
- **Satu sumber logika** untuk live & backtest (package `traderadar.engine`).
- **Idempotensi event:** konsumer Redis Stream harus aman di-replay (upsert berdasarkan `event_id`).
- **Kegagalan anggun:** sumber eksternal mati → fallback/NA + status di UI, tidak crash. Setiap service punya healthcheck.
- **Keamanan:** secret hanya dari `.env`; jangan commit `.env`, `backups/`; host port hanya `127.0.0.1`; semua endpoint kecuali login/health butuh auth.
- **Bahasa:** kode/commit English; teks UI, Telegram, komentar AI, pesan error untuk user → Bahasa Indonesia.
- **Waktu:** simpan UTC (`timestamptz`); tampilkan WIB (`Asia/Jakarta`).
- **Pin versi** semua image & dependency; catat pilihan versi di `docs/DECISIONS.md`.
- **Verifikasi asumsi eksternal** (simbol `XAUUSDT` di Binance, nama model Gemini, format feed kalender) di awal fase terkait dan catat hasilnya di `docs/DECISIONS.md`. Bila spesifikasi ambigu, pilih opsi paling aman/sederhana, catat, lanjut.
- **Test wajib:** lihat `SIGNAL_ENGINE.md` §9; coverage `engine/` ≥ 85%.

## Perintah standar
```bat
start.bat                                   :: user: nyalakan semua (http://localhost:8080)
docker compose -f compose.yaml -f compose.dev.yaml up --build   :: dev: hot reload, Vite di :5173
docker compose run --rm api pytest          :: test backend
cd frontend && npm run lint && npm run test && npm run gen:api
```
