# Infrastruktur — Docker Desktop

Target: Windows + Docker Desktop (backend WSL2), RAM 16 GB. Satu perintah menyalakan semua: `start.bat` → `docker compose up -d --build`.

## 1. Prinsip
- Satu image Python `traderadar-py` untuk semua service Python (entrypoint berbeda) → build sekali, konsisten.
- Image multi-stage, user non-root, `HEALTHCHECK` di setiap service, `restart: unless-stopped`.
- Hanya `proxy` yang membuka port, dan hanya ke `127.0.0.1`.
- Pin semua tag image ke versi spesifik (bukan `latest`) — agent memilih versi stabil terbaru saat Fase 0 dan mencatatnya di `DECISIONS.md`.
- Konfigurasi dari `.env` + `config/settings.yaml` (di-mount read-only).
- Zona waktu container `UTC`; konversi WIB hanya di presentasi.

## 2. `compose.yaml` (kerangka — agent melengkapi)

```yaml
name: traderadar

x-py: &py
  image: traderadar-py:${APP_VERSION:-dev}
  build: { context: ., dockerfile: infra/docker/python.Dockerfile }
  env_file: .env
  environment:
    DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
    REDIS_URL: redis://redis:6379/0
    TZ: UTC
  volumes:
    - ./config:/app/config:ro
    - models:/app/models
  depends_on:
    db: { condition: service_healthy }
    redis: { condition: service_healthy }
    migrate: { condition: service_completed_successfully }
  restart: unless-stopped
  logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }

services:
  db:
    image: timescale/timescaledb:<pin>-pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    command: ["postgres", "-c", "shared_buffers=256MB", "-c", "max_connections=60"]
    volumes: [pgdata:/var/lib/postgresql/data, ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"], interval: 5s, retries: 20 }
    deploy: { resources: { limits: { memory: 768m } } }
    restart: unless-stopped

  redis:
    image: redis:<pin>-alpine
    command: ["redis-server", "--appendonly", "yes", "--maxmemory", "96mb", "--maxmemory-policy", "noeviction"]
    volumes: [redisdata:/data]
    healthcheck: { test: ["CMD", "redis-cli", "ping"], interval: 5s, retries: 20 }
    deploy: { resources: { limits: { memory: 128m } } }
    restart: unless-stopped

  migrate:
    <<: *py
    command: ["python", "-m", "traderadar.services.migrate"]   # alembic upgrade + seed admin + settings
    depends_on:
      db: { condition: service_healthy }
    restart: "no"

  api:
    <<: *py
    command: ["uvicorn", "traderadar.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
    healthcheck: { test: ["CMD", "python", "-m", "traderadar.healthcheck", "api"], interval: 15s }
    deploy: { resources: { limits: { memory: 384m } } }

  ingestor:
    <<: *py
    command: ["python", "-m", "traderadar.services.ingestor"]
    deploy: { resources: { limits: { memory: 384m } } }

  engine:
    <<: *py
    command: ["python", "-m", "traderadar.services.engine"]
    deploy: { resources: { limits: { memory: 512m } } }

  worker:
    <<: *py
    command: ["arq", "traderadar.services.worker.WorkerSettings"]
    deploy: { resources: { limits: { memory: 1g } } }

  scheduler:
    <<: *py
    command: ["arq", "traderadar.services.scheduler.SchedulerSettings"]
    volumes: [./config:/app/config:ro, ./backups:/app/backups]
    deploy: { resources: { limits: { memory: 128m } } }

  telegram:
    <<: *py
    command: ["python", "-m", "traderadar.services.telegram"]
    deploy: { resources: { limits: { memory: 192m } } }

  proxy:
    image: traderadar-web:${APP_VERSION:-dev}
    build: { context: ., dockerfile: infra/docker/web.Dockerfile }   # stage 1 node build, stage 2 caddy
    ports: ["127.0.0.1:${APP_PORT:-8080}:80"]
    depends_on: [api]
    deploy: { resources: { limits: { memory: 64m } } }
    restart: unless-stopped

  prometheus:
    profiles: [monitoring]
    image: prom/prometheus:<pin>
    volumes: [./infra/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro]
  grafana:
    profiles: [monitoring]
    image: grafana/grafana:<pin>
    ports: ["127.0.0.1:3001:3000"]

volumes: { pgdata: {}, redisdata: {}, models: {} }
```

`compose.dev.yaml`: mount `backend/src` & jalankan `uvicorn --reload` / `watchfiles` untuk service Python; service `web-dev` (Vite di `127.0.0.1:5173`, proxy ke api); buka port db `127.0.0.1:5433` untuk inspeksi.

## 3. Dockerfile Python (garis besar)
```dockerfile
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:<pin> /uv /bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*   # lightgbm
RUN useradd -m app
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
```

## 4. Caddyfile
```
:80 {
  encode zstd gzip
  handle /api/* { reverse_proxy api:8000 }
  handle /ws    { reverse_proxy api:8000 }
  handle {
    root * /srv
    try_files {path} /index.html
    file_server
  }
  header {
    X-Content-Type-Options nosniff
    X-Frame-Options DENY
    Referrer-Policy strict-origin-when-cross-origin
    Content-Security-Policy "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'"
  }
}
```
Font (Inter, JetBrains Mono) di-bundle lokal lewat `@fontsource` agar CSP tetap `self`. Untuk VPS: ganti `:80` dengan domain → HTTPS otomatis.

## 5. Skrip pembungkus (root repo, untuk user)
| File | Isi |
|---|---|
| `start.bat` | Cek Docker Desktop berjalan (`docker info`; bila tidak → pesan "Buka Docker Desktop dulu" dan coba jalankan `Docker Desktop.exe`), cek `.env` ada (bila tidak → salin dari `.env.example`, buka Notepad, berhenti), `docker compose up -d --build`, tunggu `/api/health` hijau (maks 3 mnt, tampilkan progres), buka `http://localhost:8080`. |
| `stop.bat` | `docker compose stop` |
| `update.bat` | `git pull` (bila repo git) → `docker compose up -d --build` |
| `logs.bat` | `docker compose logs -f --tail=100 api engine ingestor worker telegram` |
| `backup.bat` | Jalankan job backup segera → file di `./backups` |
| `reset-data.bat` | Konfirmasi ketik `HAPUS` → `docker compose down -v` (menghapus semua data) |

Semua pesan skrip dalam Bahasa Indonesia.

## 6. CI (`.github/workflows/ci.yml`)
Job: `ruff` + `mypy` + `pytest` (dengan service Postgres/Timescale & Redis) · `eslint` + `tsc` + `vitest` · build kedua image · (opsional) Playwright e2e terhadap `docker compose up`.

## 7. Sumber daya & kinerja
- Total limit default ≈ 3,6 GB; sarankan Docker Desktop → Settings → Resources (WSL: file `.wslconfig`) `memory=6GB`, `processors=4`.
- Engine menghitung indikator secara inkremental per bar close (bukan seluruh histori) — target < 300 ms per simbol per TF.
- Backtest & training ML di `worker` dengan `max_jobs=2` agar tidak mengganggu live.
