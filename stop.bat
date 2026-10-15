@echo off
title TradeRadar Stopper

echo Menghentikan container TradeRadar...
docker compose stop
echo.
echo Container telah dihentikan. Data database dan cache tetap aman tersimpan.
timeout /t 3 >nul
