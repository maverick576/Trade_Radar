# UI Spec — Antarmuka Profesional TradeRadar

Target rasa: terminal trading modern (setara TradingView / Linear / Vercel dashboard) — padat informasi tapi tenang, cepat, konsisten. Bahasa UI: **Indonesia**. Format angka `id-ID` (`2.651,05`), waktu WIB (`07:15 WIB`), harga mengikuti tick size simbol.

## 1. Design system
- **Basis:** Tailwind + shadcn/ui (Radix). Semua komponen dari `components/ui/`, tidak ada styling ad-hoc di halaman.
- **Tema:** gelap default, terang tersedia, ikuti sistem bila "Otomatis". Token CSS variable:

| Token | Gelap | Terang | Pakai |
|---|---|---|---|
| `--bg` | `#0B0E14` | `#F7F8FA` | latar |
| `--surface` | `#121722` | `#FFFFFF` | kartu/panel |
| `--surface-2` | `#1A2030` | `#F0F2F5` | hover, input |
| `--border` | `#232A3A` | `#E2E5EA` | garis |
| `--fg` | `#E6E9EF` | `#111827` | teks utama |
| `--muted` | `#8A93A6` | `#6B7280` | teks sekunder |
| `--bull` | `#22C55E` | `#15803D` | BULL/LONG/profit |
| `--bear` | `#EF4444` | `#B91C1C` | BEAR/SHORT/loss |
| `--neutral` | `#64748B` | `#64748B` | NEUTRAL |
| `--warn` | `#F59E0B` | `#B45309` | macro filter gagal, berita |
| `--accent` | `#3B82F6` | `#2563EB` | aksi utama, fokus |

  Warna tidak boleh jadi satu-satunya penanda: BULL/BEAR selalu disertai ikon (▲/▼) atau teks.
- **Tipografi:** Inter (UI) + JetBrains Mono (angka, harga, tabel — `font-variant-numeric: tabular-nums`). Skala 12/13/14/16/20/24/32.
- **Spasi & bentuk:** grid 4 px, radius 8 px (kartu 12 px), border 1 px, bayangan minimal.
- **Ikon:** lucide-react. Kategori indikator: Trend `TrendingUp`, Momentum `Gauge`, Order flow `Waves`, Derivatif `Layers`, Mikro `BookOpen`, ML `Brain`, Sentimen `Smile`.
- **Motion:** 150–200 ms, `prefers-reduced-motion` dihormati. Harga berkedip hijau/merah 300 ms saat berubah.

## 2. Pola aplikasi
- **Shell:** sidebar kiri dapat diciutkan (ikon + label), topbar: pemilih simbol, indikator koneksi live (titik hijau/kuning/merah + latensi), jam WIB, countdown berita berikutnya, tombol tema, menu akun.
- **Command palette** (`Ctrl+K`): lompat ke simbol/halaman, "Minta analisa AI ETH", "Buat Brief", "Kalibrasi XAUUSD".
- **Shortcut:** `1–5` pilih simbol watchlist, `M`/`H`/`4` ganti TF, `/` cari.
- **State:** skeleton loader untuk setiap panel, empty state dengan penjelasan + aksi, error boundary per panel (satu panel gagal tidak menjatuhkan halaman), banner global untuk mode fallback data.
- **Notifikasi:** toast (sonner) untuk sinyal baru, ticket expired, TP/SL; opsional suara (diaktifkan user).
- **Responsif:** desktop utama (≥ 1280 px, layout 3 kolom), tablet 2 kolom, ponsel 1 kolom (kartu ticket & brief tetap nyaman dibaca di HP).
- **Aksesibilitas:** navigasi keyboard penuh, fokus terlihat, kontras AA, `aria-live` untuk sinyal baru.
- **Data real-time:** TanStack Query sebagai cache; event WS meng-update cache (`setQueryData`) — tidak ada polling bila WS hidup.

## 3. Halaman

### Login
Kartu tengah: logo, email, password, (kode 2FA bila aktif), pesan error jelas, rate-limit info.

### Dashboard `/`
- Baris KPI: equity paper, PnL hari ini, winrate 30 hari (paper | real), ticket aktif, kuota AI tersisa.
- **Kartu watchlist** (grid): simbol + sumber kecil, harga live, % 24j, sparkline 24 jam, **gauge skor** −100..+100, chip verdict, ringkas `5▲ 4• 1▼`, status macro (✓ / ⚠ alasan), chip bias HTF H1/H4/D1. Klik → Analisa.
- **Ticket aktif** (daftar kartu ringkas + countdown kedaluwarsa + tombol Salin).
- **Berita berikutnya** (timeline 24 jam, High = oranye).
- **Aktivitas terakhir** (feed sinyal/TP/SL).

### Brief `/brief`
Tanggal & jenis (Pagi/Siang), ringkasan umum AI, lalu per simbol: bias, level kunci (tabel), skenario, berita relevan. Tombol "Buat ulang", "Kirim ke Telegram", "Salin".

### Analisa `/analisa/:symbol` — layar terpenting (terinspirasi dashboard video 1)
Layout 3 kolom desktop:
1. **Chart** (lebar): lightweight-charts candlestick + volume; overlay toggle (EMA ribbon, VWAP ±1/2σ, Supertrend, Bollinger, EMA Strategi B); marker sinyal historis (▲▼ berwarna, tooltip skor); garis entry/SL/TP ticket aktif; pane bawah: RSI dan CVD (tab). TF tabs M15·H1·H4·D1. Label "LIVE · belum close" pada bar berjalan.
2. **Panel indikator:** 10 kartu dikelompokkan per kategori — ikon, nama, chip state, nilai utama mono, alasan 1 kalimat, tooltip definisi. NA tampil redup dengan alasan ("Tidak tersedia untuk sumber ini"). Di atas: ringkasan `Sinyal: 5 Bullish · 4 Netral · 1 Bearish`, gauge skor, verdict besar.
3. **Kolom keputusan:** checklist Macro Filter (M1–M8, ✓/✗ + detail), bias HTF, panel Strategi B, **Trade Ticket** (bila ada), **Tanggapan AI** (ringkasan, chip bias/keyakinan, setuju/tidak dengan engine, alasan, risiko, skenario bullish/bearish, invalidasi; tombol "Minta analisa AI", info provider & waktu; badge "Komentar otomatis" bila fallback).
Riwayat skor (area chart kecil 48 jam) di bawah chart.

### Ticket & Sinyal `/ticket`
- Tab **Aktif / Riwayat / Terblokir**.
- **Kartu ticket** (komponen inti, juga dipakai di Dashboard & mobile): header warna sisi, simbol, strategi, skor, countdown; tabel Entry-zona / SL / TP1 / TP2 dengan kolom *Harga sumber · Harga broker (terkalibrasi) · Jarak*; kalkulator lot (pilih profil broker, saldo, risiko % → lot + risiko aktual, peringatan min lot); invalidasi; alasan & risiko; tombol **Salin lengkap / Salin ringkas / Saya eksekusi / Lewati**.
- Dialog **Kalibrasi broker**: input harga broker sekarang → offset + masa berlaku.
- Dialog **Saya eksekusi**: harga fill, lot, waktu (default sekarang) → masuk Jurnal Real. Dialog **Tutup posisi** untuk exit.
- Tab Terblokir: sinyal + alasan blokir + hasil virtual.

### Posisi Paper `/paper`
Tabel posisi terbuka (floating R & USD live), tertutup, equity curve.

### Jurnal `/jurnal`
Toggle **Paper | Real | Bandingkan**. KPI (winrate, PF, expectancy R, max DD, jumlah trade), equity curve, distribusi R (histogram), heatmap jam×hari, breakdown tabel (simbol/strategi/sesi/verdict), **akurasi per indikator** (bar chart winrate searah vs berlawanan), **nilai macro filter** (sinyal terblokir vs diambil), **slippage nyata**. Filter rentang tanggal. Ekspor CSV. Tiap baris trade bisa dibuka → snapshot analisis saat itu.

### Backtest `/backtest`
Form (simbol, strategi A/B/keduanya, rentang, TF, sumber data, override bobot/threshold) → progres live → laporan (KPI, equity vs buy&hold, drawdown, daftar trade, catatan indikator NA, peringatan overfitting). Daftar run sebelumnya + bandingkan 2 run.

### Kalender `/kalender`
Daftar per hari (WIB), filter impact/mata uang, badge "blackout", forecast/previous/actual.

### Status `/status`
Kartu per service (online, uptime, lag), sumber data aktif per simbol, kuota AI (bar), status Telegram, ukuran DB, backup terakhir, versi aplikasi.

### Pengaturan `/pengaturan`
Tab: **Watchlist** (≤ 5, sumber Gold) · **Strategi** (bobot dengan total live = 100, threshold, Strategi B) · **Risiko & Paper** · **Broker** (profil: nama, contract size per simbol, min/step lot, mata uang) · **AI** (provider, model, batas RPM/RPD, tes koneksi) · **Telegram** (status, kirim pesan uji, jadwal brief/rekap) · **Akun** (ganti password, 2FA) · **Tampilan**. Setiap perubahan strategi menaikkan `weights_version` dan meminta konfirmasi.

## 4. Kualitas frontend
- TypeScript strict, tanpa `any`. Tipe API dari OpenAPI (`npm run gen:api`).
- Struktur per fitur (`features/tickets/{api,components,hooks}`).
- Vitest untuk util/format & komponen kunci (TicketCard, IndicatorCard, ScoreGauge); Playwright: login → dashboard → buka analisa → salin ticket → eksekusi → jurnal.
- Lighthouse desktop: Performance ≥ 90, Accessibility ≥ 95. Bundle awal < 300 kB gzip (code-split per route, chart dimuat lazy).
