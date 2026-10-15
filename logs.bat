@echo off
title TradeRadar Logs

echo Menampilkan log container TradeRadar (Tekan Ctrl+C untuk keluar)...
docker compose logs -f --tail=100 api engine ingestor worker scheduler telegram db redis proxy
