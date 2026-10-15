@echo off
setlocal enabledelayedexpansion
title TradeRadar Backup

echo Membuat backup database TradeRadar...

if not exist "backups" mkdir "backups"

for /f "tokens=2 delims==" %%I in ('findstr "POSTGRES_USER" .env') do set DB_USER=%%I
for /f "tokens=2 delims==" %%I in ('findstr "POSTGRES_DB" .env') do set DB_NAME=%%I

if "!DB_USER!"=="" set DB_USER=traderadar
if "!DB_NAME!"=="" set DB_NAME=traderadar

set BACKUP_FILE=backups\traderadar_%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.sql
set BACKUP_FILE=%BACKUP_FILE: =0%

echo Menyimpan database !DB_NAME! ke !BACKUP_FILE! ...
docker compose exec -T db pg_dump -U !DB_USER! -d !DB_NAME! > "!BACKUP_FILE!"

if %errorlevel% equ 0 (
    echo [OK] Backup berhasil disimpan: !BACKUP_FILE!
) else (
    echo [ERROR] Gagal membuat backup database. Pastikan container db sedang aktif.
)

pause
