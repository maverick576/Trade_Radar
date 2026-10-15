# TradeRadar

> Web application profesional untuk analisis market real-time (crypto + Gold), sinyal konfluensi multi-indikator, komentar AI (Gemini), Trade Ticket untuk eksekusi manual, paper trading, jurnal winrate, backtest, kalender berita, dan bot Telegram dua arah.

## Panduan Cepat (Windows)

1. Pastikan **Docker Desktop** sudah berjalan.
2. Dobel-klik `start.bat`.
3. Pada run pertama, file `.env` akan dibuat dari `.env.example`. Isi nilai yang dibutuhkan (terutama `POSTGRES_PASSWORD`, `SECRET_KEY`, `ADMIN_PASSWORD`), lalu jalankan `start.bat` kembali.
4. Buka browser di [http://localhost:8080](http://localhost:8080).

Lihat detail lengkap di:
- [Panduan Setup Windows](file:///docs/SETUP_WINDOWS.md)
- [Blueprint Arsitektur](file:///docs/BLUEPRINT.md)
- [Signal Engine](file:///docs/SIGNAL_ENGINE.md)
- [Dokumentasi Docker & Infra](file:///docs/INFRA_DOCKER.md)
