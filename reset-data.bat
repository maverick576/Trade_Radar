@echo off
setlocal
title TradeRadar Data Reset

echo ========================================================
echo               PERINGATAN RESET DATA
echo ========================================================
echo Tindakan ini akan MENGHAPUS SEMUA DATA di database Postgres
echo dan antrean Redis (termasuk riwayat trading, candle, dan akun).
echo.
set /p CONFIRM="Ketik 'HAPUS' dengan huruf kapital untuk konfirmasi: "

if "%CONFIRM%"=="HAPUS" (
    echo.
    echo Menghapus container dan volume data...
    docker compose down -v
    echo.
    echo [OK] Semua data TradeRadar telah dibersihkan.
) else (
    echo.
    echo Pembatalan: Konfirmasi tidak cocok. Data tetap aman.
)

pause
