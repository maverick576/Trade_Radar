# Sumber Data, Database, Event, dan API

## 1. Sumber Data Eksternal (semua web, tanpa MetaTrader)

Semua base URL di `.env`. Data market Binance = **endpoint publik, tanpa API key**.

### 1.1 Binance USDT-M Futures — crypto & Gold (`XAUUSDT`)
| Data | Endpoint | Frekuensi |
|---|---|---|
| Info simbol | `GET {BINANCE_FAPI}/fapi/v1/exchangeInfo` | Start + tiap 6 jam |
| Kline historis | `GET /fapi/v1/klines?symbol=&interval=15m&limit=1500&startTime=` | Backfill & backtest |
| Kline live | `{BINANCE_FSTREAM}/stream?streams=xauusdt@kline_15m/...` | WebSocket |
| Order book | stream `<sym>@depth20@500ms` | WebSocket |
| Mark price & funding | stream `<sym>@markPrice@1s` | WebSocket |
| Open interest histori | `GET /futures/data/openInterestHist?symbol=&period=15m&limit=500` | 5 mnt (±30 hari histori) |
| Long/short ratio | `GET /futures/data/globalLongShortAccountRatio?symbol=&period=15m` | 5 mnt |

- Field kline index 9 = taker buy base volume → CVD.
- Satu koneksi WS maks 1024 stream & diputus Binance tiap 24 jam → reconnect terjadwal tiap 23 jam.
- **Gold `XAUUSDT`** adalah kontrak TradFi perpetual (diluncurkan Jan 2026). Agent wajib memverifikasi saat Fase 1 bahwa simbol muncul di `exchangeInfo` publik dan semua endpoint di atas merespons untuknya; catat hasil di `docs/DECISIONS.md`. Bila tidak tersedia → fallback berikut.

### 1.2 Fallback & opsional
| Sumber | Endpoint | Kapan |
|---|---|---|
| Binance Spot `PAXGUSDT` | `{BINANCE_SPOT}/api/v3/klines`, stream `paxgusdt@kline_15m` di `{BINANCE_SPOT_STREAM}` | Fallback Gold otomatis |
| Binance data mirror | `https://data-api.binance.vision` | Bila `api.binance.com` terblokir (spot saja) |
| OANDA v20 practice | `https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles` (maks 5000/request), stream `https://stream-fxpractice.oanda.com/v3/accounts/{id}/pricing/stream` | Opsional bila `OANDA_API_TOKEN` diisi (akun demo gratis) |
| Dukascopy | Data historis XAU/USD (unduh via loader backtest) | Backtest/ML Gold > histori Binance |
| Binance bulk | `https://data.binance.vision/` (zip CSV bulanan) | Backtest panjang crypto |

### 1.3 Lainnya
| Data | Sumber | Key |
|---|---|---|
| Fear & Greed | `https://api.alternative.me/fng/?limit=30` | Tidak |
| Kalender ekonomi | `https://nfs.faireconomy.media/ff_calendar_thisweek.json` (feed tidak resmi; tangani gagal) | Tidak |
| Kalender cadangan | Finnhub `GET /api/v1/calendar/economic` | Ya (gratis) |
| AI | Gemini API (`google-genai`) | Ya (Google AI Studio) |
| Telegram | Bot API | Token @BotFather |

---

## 2. Database — PostgreSQL 16 + TimescaleDB

Waktu disimpan sebagai `timestamptz` (UTC). Uang/harga `numeric(20,8)` di tabel transaksi; `double precision` di candles demi performa. Migrasi Alembic.

```sql
-- Hypertable (chunk 7 hari, kompresi setelah 30 hari)
candles(symbol text, tf text, open_time timestamptz, open, high, low, close, volume float8,
        taker_buy_volume float8 null, source text, PRIMARY KEY(symbol, tf, open_time))
derivatives_snapshots(symbol, ts timestamptz, funding, mark, open_interest, ls_ratio, PK(symbol, ts))   -- hypertable
sentiment_snapshots(source, ts, value, label, PK(source, ts))

analyses(id bigserial PK, symbol, tf, bar_time timestamptz, source text, score float8, verdict text,
         counts jsonb, indicators jsonb, category_votes jsonb, htf jsonb, macro jsonb,
         strategy_b jsonb, weights_version text, created_at, UNIQUE(symbol, tf, bar_time))

signals(id bigserial PK, analysis_id FK, strategy text, symbol, tf, side text, verdict text,
        bar_time, status text,              -- blocked|ticketed|expired
        blocked_by text[] null, confirmed_by_b bool, created_at)

tickets(id bigserial PK, signal_id FK UNIQUE, symbol, side, source text,
        entry, entry_low, entry_high, sl, tp1, tp2 numeric, atr numeric,
        invalidation text, reasons jsonb, risks jsonb,
        valid_until timestamptz, status text,  -- new|executed|skipped|expired|closed
        broker_offset numeric null, broker_profile text null, suggested_lot numeric null,
        created_at, updated_at)

real_executions(id bigserial PK, ticket_id FK, broker_profile text, fill_price numeric, lot numeric,
        fill_time timestamptz, exit_price numeric null, exit_time null, pnl_usd numeric null,
        pnl_r numeric null, slippage_points numeric, notes text, source text) -- source: ui|telegram

paper_trades(id bigserial PK, ticket_id FK null, strategy, symbol, side, entry_time, entry_price,
        size, sl, tp1, tp2, exit_time, exit_price, exit_reason, pnl_usd, pnl_r, fees_usd,
        mfe_r, mae_r, is_virtual bool default false)   -- virtual = simulasi sinyal terblokir

broker_calibrations(id, symbol, broker_profile, broker_price, source_price, offset, created_at, expires_at)

ai_comments(id, analysis_id FK null, brief_id FK null, kind text, provider, model, content jsonb,
            valid bool, latency_ms int, tokens_in int, tokens_out int, created_at)
market_briefs(id, kind text, generated_at, payload jsonb, narrative jsonb)
news_events(id text PK, ts, currency, impact, title, forecast, previous, actual, source)
backtest_runs(id, params jsonb, status, progress, metrics jsonb, equity jsonb, created_at, finished_at)
backtest_trades(run_id FK, ... sama dgn paper_trades)
ml_models(id, symbol, version, path, trained_at, train_from, train_to, metrics jsonb, active bool)

users(id, email unique, password_hash, totp_secret null, last_login_at, created_at)
refresh_tokens(id, user_id, token_hash, expires_at, revoked_at)
audit_log(id, user_id, action, detail jsonb, ip, created_at)
app_settings(key PK, value jsonb, version int, updated_at)
telegram_chats(chat_id bigint PK, username, paused bool, created_at)
```

Continuous aggregate: statistik harian paper/real untuk Jurnal. Retensi: candles M15 2 tahun (kompresi), analyses 180 hari; transaksi selamanya.

---

## 3. Event Bus (Redis)

| Nama | Tipe | Produsen → Konsumen | Payload |
|---|---|---|---|
| `candles.closed` | Stream (consumer group `engine`) | ingestor → engine | `{event_id, symbol, tf, bar_time, source}` |
| `signals` | Stream (group `telegram`, `worker`) | engine → telegram, worker | `{signal_id, ticket_id, verdict, symbol}` |
| `ai.requests` | arq queue | api/engine/scheduler → worker | `{kind, ref_id}` |
| `ticks:<symbol>` | Pub/Sub | ingestor → engine, api(WS) | `{price, ts}` (throttle 4/dtk) |
| `ui.events` | Pub/Sub | semua → api(WS fan-out) | `{type, data}` |
| `status:<service>` | key TTL 30 dtk | semua → api | heartbeat + metrik singkat |

Semua skema event didefinisikan sekali di `core/events.py` (Pydantic), dipakai produsen & konsumen.

---

## 4. REST API (`/api`, OpenAPI di `/api/docs` hanya saat dev)

Semua endpoint kecuali `auth/login` & `health` butuh sesi login.

| Method | Path | Deskripsi |
|---|---|---|
| POST | `/auth/login` · `/auth/logout` · `/auth/refresh` | Sesi cookie |
| GET | `/auth/me` · PUT `/auth/password` · POST `/auth/totp/setup` | Akun admin |
| GET | `/health` · `/health/full` | Status |
| GET | `/symbols` | Watchlist + sumber aktif + kapabilitas + harga |
| GET | `/candles?symbol=&tf=&limit=` | Candle closed + bar berjalan |
| GET | `/analysis/{symbol}?tf=` · `/analysis/{symbol}/history` | Analisis terbaru/riwayat skor |
| POST | `/analysis/{symbol}/ai?tf=` | Minta komentar AI |
| GET | `/briefs/latest` · POST `/briefs` | Market Brief |
| GET | `/tickets?status=` · `/tickets/{id}` | Ticket |
| POST | `/tickets/{id}/execute` | `{fill_price, lot, broker_profile, fill_time?}` |
| POST | `/tickets/{id}/close` | `{exit_price, exit_time?}` |
| POST | `/tickets/{id}/skip` | |
| POST | `/calibrations` | `{symbol, broker_profile, broker_price}` → offset |
| GET | `/signals?…` · `/signals/{id}` | Sinyal (termasuk terblokir) |
| GET | `/paper/trades?status=` · POST `/paper/trades/{id}/close` | Paper |
| GET | `/stats?book=paper|real&range=&strategy=&group_by=` · `/stats/export.csv` | Jurnal |
| GET | `/news?from=&to=&impact=` | Kalender |
| POST | `/backtests` · GET `/backtests` · `/backtests/{id}` | Backtest |
| POST | `/ml/train?symbol=` · GET `/ml/models` | ML |
| GET/PUT | `/settings` · POST `/settings/telegram/test` | Setelan (validasi Pydantic, watchlist ≤ 5) |

Error seragam: `{"error": {"code": "SOURCE_UNAVAILABLE", "message": "Data XAUUSDT dari Binance terputus, memakai PAXGUSDT sementara.", "detail": {...}}}`

## 5. WebSocket `/ws`
Auth via cookie. Klien: `{"type":"subscribe","symbols":[...],"tfs":[...]}`. Server: `tick`, `candle`, `analysis`, `preview`, `signal`, `ticket`, `ai_comment`, `paper_trade`, `news`, `status`, `backtest_progress`, `brief`. Ping 20 dtk; klien auto-reconnect + re-subscribe + refetch query yang terlewat.
