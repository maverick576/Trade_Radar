# Stage 1: Build React/TS SPA
FROM node:22.14-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Caddy server
FROM caddy:2.9.1-alpine

COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/dist /srv

EXPOSE 80
