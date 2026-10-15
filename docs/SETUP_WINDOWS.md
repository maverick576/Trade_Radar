# Panduan Setup TradeRadar di Docker Desktop (Windows)

Ikuti sekali. Setelah itu cukup dobel-klik `start.bat`.

## 1. Install Docker Desktop
1. Unduh dari https://www.docker.com/products/docker-desktop/ → install dengan opsi **Use WSL 2** (default).
2. Restart PC bila diminta, buka Docker Desktop, tunggu status **Engine running** (ikon paus hijau).
3. Batasi memori agar PC tetap lancar: buat file `C:\Users\<nama>\.wslconfig` berisi:
   ```
   [wsl2]
   memory=6GB
   processors=4
   ```
   lalu jalankan `wsl --shutdown` di Command Prompt dan buka ulang Docker Desktop.
4. (Opsional) Settings → General → centang *Start Docker Desktop when you sign in* agar aplikasi bisa jalan otomatis.

## 2. Siapkan kunci & akun
| Yang dibutuhkan | Cara | Isi di `.env` |
|---|---|---|
| Akun admin aplikasi | Tentukan email & password (≥ 12 karakter) | `ADMIN_EMAIL`, `ADMIN_PASSWORD` |
| Password database | Bebas, acak | `POSTGRES_PASSWORD` |
| Secret sesi | Teks acak ≥ 32 karakter | `SECRET_KEY` |
| Gemini API key | https://aistudio.google.com → *Get API key* → *Create API key*. Cek juga nama model yang tersedia | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Bot Telegram | Chat **@BotFather** → `/newbot` → salin token | `TELEGRAM_BOT_TOKEN` |
| Chat ID Telegram | Setelah aplikasi jalan, kirim `/start` ke bot → bot membalas chat_id → isi lalu `start.bat` lagi | `TELEGRAM_ALLOWED_CHAT_IDS` |
| (Opsional) OANDA | Daftar akun demo/practice OANDA → *Manage API Access* → token | `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID` |
| (Opsional) Finnhub | https://finnhub.io → free API key (cadangan kalender) | `FINNHUB_API_KEY` |

Data Binance (crypto & Gold) **tidak butuh akun atau key**.

## 3. Jalankan
1. Dobel-klik `start.bat`. Pada run pertama, skrip menyalin `.env.example` → `.env` dan membukanya di Notepad — isi tabel di atas, simpan, lalu dobel-klik `start.bat` lagi.
2. Build pertama 5–15 menit (mengunduh image). Berikutnya < 1 menit.
3. Browser terbuka di **http://localhost:8080** → login dengan akun admin.
4. Buka halaman **Status**: semua service hijau, sumber Gold terlihat (mis. "Binance XAUUSDT").
5. Di **Pengaturan → Broker**, cek profil Exness (Gold 100 oz/lot, min 0,01) dan isi saldo akun Anda untuk kalkulator lot.

## 4. Pemakaian harian
- Pagi: baca **Brief** (juga dikirim ke Telegram 06:45 WIB).
- Saat ada ticket: buka kartu ticket → (disarankan) **Kalibrasi** dengan harga Exness saat itu → salin → eksekusi manual di Exness → tekan **Saya eksekusi** dan isi harga fill & lot. Bisa juga semuanya lewat Telegram.
- Setelah posisi selesai → **Tutup posisi** dengan harga exit, agar Jurnal Real akurat.

## 5. Skrip
| Skrip | Fungsi |
|---|---|
| `start.bat` | Nyalakan/perbarui semua container |
| `stop.bat` | Matikan (data aman) |
| `logs.bat` | Lihat log |
| `backup.bat` | Backup database ke folder `backups\` |
| `update.bat` | Ambil versi terbaru & build ulang |
| `reset-data.bat` | Hapus SEMUA data (minta konfirmasi) |

## 6. Masalah umum
| Gejala | Solusi |
|---|---|
| "Docker tidak berjalan" | Buka Docker Desktop, tunggu Engine running, ulangi `start.bat` |
| Port 8080 dipakai | Ubah `APP_PORT` di `.env` (mis. 8090) |
| Gold memakai PAXGUSDT | Sumber XAUUSDT sedang tidak tersedia; normal, harga bisa beda beberapa dolar — pakai Kalibrasi |
| Data futures tidak muncul | Jaringan memblok `fapi.binance.com`; aplikasi pindah ke spot (funding/OI jadi NA). Coba DNS 1.1.1.1 atau jaringan lain |
| AI "kuota habis" | Tunggu reset harian / turunkan `AI_MAX_RPD`; komentar otomatis tetap muncul |
| Telegram diam | Pastikan chat_id di `.env`, lalu `start.bat` lagi |
| PC berat | Turunkan `memory` di `.wslconfig` ke 4GB, jangan aktifkan profil monitoring |
