@echo off
title TradeRadar Updater

echo Memperbarui TradeRadar...
if exist ".git" (
    echo Mengambil update terbaru dari Git...
    git pull
)

echo Membangun ulang dan menyalakan container...
docker compose up -d --build
echo.
echo TradeRadar berhasil diperbarui!
timeout /t 5 >nul
