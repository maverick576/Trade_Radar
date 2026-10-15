@echo off
setlocal enabledelayedexpansion
title TradeRadar Launcher

echo ========================================================
echo               TRADERADAR LAUNCHER
echo ========================================================
echo.

:: 1. Cek Docker Desktop
echo [1/4] Memeriksa Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker Desktop belum berjalan. Mencoba menyalakan Docker Desktop...
    if exist "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe" (
        start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
    ) else if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    ) else (
        echo [ERROR] Docker Desktop.exe tidak ditemukan! Silakan buka Docker Desktop secara manual.
        pause
        exit /b 1
    )

    echo Menunggu engine Docker siap (maks 90 detik)...
    set /a DOCKER_WAIT=0
    :wait_docker_loop
    timeout /t 3 /nobreak >nul
    set /a DOCKER_WAIT+=3
    docker info >nul 2>&1
    if %errorlevel% equ 0 goto docker_ready
    if !DOCKER_WAIT! geq 90 (
        echo [ERROR] Waktu tunggu habis. Pastikan Docker Desktop terbuka dan status 'Engine running'.
        pause
        exit /b 1
    )
    echo   Menunggu... (!DOCKER_WAIT!s)
    goto wait_docker_loop
)

:docker_ready
echo [OK] Docker Desktop aktif.
echo.

:: 2. Cek file .env
echo [2/4] Memeriksa konfigurasi .env...
if not exist ".env" (
    echo File .env belum ditemukan. Menyalin template dari .env.example...
    copy ".env.example" ".env" >nul
    echo.
    echo ========================================================
    echo PERHATIAN: Silakan isi kredensial di Notepad yang terbuka:
    echo - ADMIN_PASSWORD (minimal 12 karakter)
    echo - POSTGRES_PASSWORD
    echo - SECRET_KEY (acak minimal 32 karakter)
    echo Setelah selesai mengisi dan menyimpan, jalankan kembali start.bat
    echo ========================================================
    notepad .env
    pause
    exit /b 0
)

if not exist "config\settings.yaml" (
    if exist "config\settings.example.yaml" (
        copy "config\settings.example.yaml" "config\settings.yaml" >nul
    )
)
echo [OK] Konfigurasi tersedia.
echo.

:: 3. Build dan Jalankan Container
echo [3/4] Menjalankan Docker Compose (build bila ada perubahan)...
docker compose up -d --build
if %errorlevel% neq 0 (
    echo [ERROR] Gagal menjalankan container Docker Compose!
    pause
    exit /b 1
)
echo [OK] Container berhasil dijalankan.
echo.

:: 4. Tunggu healthcheck
echo [4/4] Menunggu semua service online (maksimal 3 menit)...
set /a WAIT_SEC=0
:health_loop
timeout /t 3 /nobreak >nul
set /a WAIT_SEC+=3

curl -s -f http://127.0.0.1:8080/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] TradeRadar siap dan sehat! (dalam !WAIT_SEC! detik)
    echo.
    echo Membuka browser ke http://localhost:8080 ...
    start http://localhost:8080
    goto end
)

if !WAIT_SEC! geq 180 (
    echo [WARN] Waktu tunggu 3 menit tercapai. Silakan periksa log dengan logs.bat
    pause
    exit /b 1
)

echo   Menunggu service siap... (!WAIT_SEC! detik)
goto health_loop

:end
echo.
echo TradeRadar berjalan di latar belakang.
echo Untuk melihat log: dobel-klik logs.bat
echo Untuk menghentikan: dobel-klik stop.bat
timeout /t 5 >nul
