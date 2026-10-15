FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /bin/uv

WORKDIR /app

# Salin definisi dependency terlebih dahulu untuk caching layer
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --extra dev --no-install-project

# Salin source code backend dan selesaikan instalasi package
COPY backend/ ./
RUN uv sync --frozen --extra dev

# Stage runtime produksi
FROM python:3.12-slim

# Install dependency sistem untuk library numerik/ML (libgomp1) dan utilitas runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /bin/uv

# Non-root user demi keamanan
RUN useradd -m -u 1000 app

WORKDIR /app

# Salin environment dari stage builder
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

USER app

