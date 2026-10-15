"""Market data Ingestor service.

Orchestrates:
- Binance WebSocket streams (kline, depth, markPrice)
- Historical backfill & gap recovery
- Gold failover management (XAUUSDT -> PAXGUSDT)
- Redis Stream (candles.closed) & PubSub (ticks, ui.events) dispatch
- Periodic derivatives and sentiment polling
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any

from traderadar.core.config import get_settings
from traderadar.core.db import get_db_session
from traderadar.core.events import STREAM_CANDLES_CLOSED
from traderadar.core.logging import get_logger
from traderadar.core.redis import get_redis
from traderadar.core.time import to_iso_utc, utc_now
from traderadar.services.binance import BinanceConnector
from traderadar.services.candle_store import (
    get_latest_candle,
    insert_derivatives_snapshot,
    insert_sentiment_snapshot,
    upsert_candles,
)
from traderadar.services.gold_source import GoldSourceManager
from traderadar.services.runner import run_service

logger = get_logger("traderadar.ingestor")


class MarketDataIngestor:
    """Core market data ingestor coordinating WebSocket, REST backfill, and persistence."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.connector = BinanceConnector()
        self.gold_manager = GoldSourceManager()
        self.is_running = False

        # Watchlist symbols
        self.crypto_symbols = [
            item.symbol for item in self.settings.app.watchlist if item.asset == "crypto"
        ]
        self.timeframes = ["M15", "H1", "H4", "D1"]

        # Tick rate limiter state: {symbol: last_emit_timestamp}
        self._last_tick_emit: dict[str, float] = {}
        self._last_live_bar_emit: dict[str, float] = {}
        self._last_gold_tick_time = time.time()

    @property
    def all_futures_symbols(self) -> list[str]:
        """List of active futures symbols (crypto + Gold if using futures)."""
        symbols = list(self.crypto_symbols)
        if self.gold_manager.active_provider == "binance_futures":
            symbols.append(self.gold_manager.active_symbol)
        return symbols

    async def initialize_backfill(self) -> None:
        """Backfill historical candles for all watchlist symbols upon startup."""
        logger.info("starting_historical_backfill", symbols=self.all_futures_symbols)
        target_bars = self.settings.app.timeframes.backfill_bars

        async with get_db_session() as session:
            # Backfill crypto futures
            for sym in self.crypto_symbols:
                for tf in self.timeframes:
                    try:
                        latest = await get_latest_candle(session, sym, tf)
                        if latest is None:
                            candles = await self.connector.backfill_symbol_tf(
                                sym, tf, target_bars=target_bars, is_futures=True
                            )
                            await upsert_candles(session, candles)
                    except Exception as exc:
                        logger.error("backfill_error", symbol=sym, tf=tf, error=str(exc))

            # Backfill gold symbol
            gold_sym = self.gold_manager.active_symbol
            is_gold_fut = self.gold_manager.active_provider == "binance_futures"
            for tf in self.timeframes:
                try:
                    latest = await get_latest_candle(session, "XAUUSD", tf)
                    if latest is None:
                        candles = await self.connector.backfill_symbol_tf(
                            gold_sym, tf, target_bars=target_bars, is_futures=is_gold_fut
                        )
                        # Normalize symbol in database to XAUUSD
                        for c in candles:
                            c["symbol"] = "XAUUSD"
                        await upsert_candles(session, candles)
                except Exception as exc:
                    logger.error("gold_backfill_error", symbol=gold_sym, tf=tf, error=str(exc))

    async def _on_candle_closed(self, candle: dict[str, Any]) -> None:
        """Handle closed candlestick: persist to DB, push to Redis stream and pubsub."""
        # Normalize Gold symbol
        db_symbol = candle["symbol"]
        if db_symbol in ("XAUUSDT", "PAXGUSDT"):
            db_symbol = "XAUUSD"

        db_candle = dict(candle)
        db_candle["symbol"] = db_symbol

        async with get_db_session() as session:
            await upsert_candles(session, [db_candle])

        # Push to Redis Stream 'candles.closed'
        r = await get_redis()
        bar_iso = to_iso_utc(candle["open_time"])
        event_id = f"{db_symbol}:{candle['tf']}:{bar_iso}"

        stream_payload = {
            "event_id": event_id,
            "symbol": db_symbol,
            "tf": candle["tf"],
            "bar_time": bar_iso,
            "source": candle["source"],
            "open": str(candle["open"]),
            "high": str(candle["high"]),
            "low": str(candle["low"]),
            "close": str(candle["close"]),
            "volume": str(candle["volume"]),
            "taker_buy_volume": str(candle["taker_buy_volume"] or 0.0),
        }
        await r.xadd(STREAM_CANDLES_CLOSED, stream_payload, maxlen=10000)

        # Notify UI clients
        ui_event = {
            "type": "candle",
            "data": {
                "symbol": db_symbol,
                "tf": candle["tf"],
                "bar": {
                    "open_time": bar_iso,
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"],
                    "is_closed": True,
                },
            },
        }
        await r.publish("ui.events", json.dumps(ui_event))
        logger.info(
            "candle_closed_persisted",
            symbol=db_symbol,
            tf=candle["tf"],
            close=candle["close"],
            bar_time=bar_iso,
        )

    async def _on_live_bar(self, symbol: str, tf: str, candle: dict[str, Any]) -> None:
        """Handle in-progress live bar with throttling."""
        db_symbol = "XAUUSD" if symbol in ("XAUUSDT", "PAXGUSDT") else symbol
        key = f"{db_symbol}:{tf}"
        now = time.time()
        last_emit = self._last_live_bar_emit.get(key, 0.0)

        if now - last_emit >= 0.5:  # Throttle to max 2/sec per symbol/tf
            self._last_live_bar_emit[key] = now
            r = await get_redis()
            bar_iso = to_iso_utc(candle["open_time"])

            # Save in Redis for rapid REST query
            cache_payload = {
                "symbol": db_symbol,
                "tf": tf,
                "open_time": bar_iso,
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
                "is_closed": False,
            }
            await r.set(f"live:bar:{db_symbol}:{tf}", json.dumps(cache_payload), ex=120)

            ui_event = {
                "type": "live_bar",
                "data": cache_payload,
            }
            await r.publish("ui.events", json.dumps(ui_event))

    async def _on_tick(self, symbol: str, price: float, ts: datetime) -> None:
        """Handle real-time price tick with 4/sec throttling per symbol."""
        db_symbol = "XAUUSD" if symbol in ("XAUUSDT", "PAXGUSDT") else symbol
        now = time.time()
        if db_symbol == "XAUUSD":
            self._last_gold_tick_time = now
            self.gold_manager.record_success()

        last_emit = self._last_tick_emit.get(db_symbol, 0.0)
        if now - last_emit >= 0.25:  # 4 ticks per second maximum
            self._last_tick_emit[db_symbol] = now
            r = await get_redis()
            iso_ts = to_iso_utc(ts)

            # Store latest price key for instant lookup
            await r.set(f"price:{db_symbol}", str(price), ex=60)

            tick_payload = {
                "symbol": db_symbol,
                "price": price,
                "ts": iso_ts,
            }
            # Publish to symbol channel and general ui.events channel
            await r.publish(f"ticks:{db_symbol}", json.dumps(tick_payload))
            await r.publish("ui.events", json.dumps({"type": "tick", "data": tick_payload}))

    async def _on_depth(
        self, symbol: str, bids: list[list[float]], asks: list[list[float]]
    ) -> None:
        """Compute best bid/ask and order book imbalance."""
        if not bids or not asks:
            return

        db_symbol = "XAUUSD" if symbol in ("XAUUSDT", "PAXGUSDT") else symbol
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread = best_ask - best_bid

        # Compute volume imbalance in top 10 levels
        bid_vol = sum(b[1] for b in bids[:10])
        ask_vol = sum(a[1] for a in asks[:10])
        total_vol = bid_vol + ask_vol
        imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

        r = await get_redis()
        payload = {
            "symbol": db_symbol,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "imbalance": round(imbalance, 4),
            "ts": to_iso_utc(utc_now()),
        }
        await r.set(f"orderbook:{db_symbol}", json.dumps(payload), ex=60)

    async def _on_mark_price(self, symbol: str, mark_price: float, funding_rate: float) -> None:
        """Update mark price and funding rate in cache."""
        db_symbol = "XAUUSD" if symbol in ("XAUUSDT", "PAXGUSDT") else symbol
        r = await get_redis()
        payload = {
            "symbol": db_symbol,
            "mark_price": mark_price,
            "funding_rate": funding_rate,
            "ts": to_iso_utc(utc_now()),
        }
        await r.set(f"mark:{db_symbol}", json.dumps(payload), ex=60)

    async def _derivatives_and_sentiment_poller(self) -> None:
        """Periodic background task (every 5 mins) to poll derivatives and Fear & Greed."""
        while self.is_running:
            try:
                # 1. Fear & Greed index
                fng_items = await self.connector.poll_fear_and_greed(limit=5)
                async with get_db_session() as session:
                    for item in fng_items:
                        await insert_sentiment_snapshot(session, {
                            "source": "alternative_me",
                            "ts": item["ts"],
                            "value": item["value"],
                            "label": item["label"],
                        })

                # 2. Derivatives for all futures symbols
                for sym in self.all_futures_symbols:
                    db_sym = "XAUUSD" if sym in ("XAUUSDT", "PAXGUSDT") else sym
                    try:
                        oi_data = await self.connector.poll_open_interest(sym)
                        ls_items = await self.connector.poll_long_short_ratio(sym, limit=1)
                        ls_ratio = (
                            float(ls_items[0].get("longShortRatio", 1.0)) if ls_items else None
                        )

                        # Fetch cached mark & funding
                        r = await get_redis()
                        mark_raw = await r.get(f"mark:{db_sym}")
                        mark_price = None
                        funding_rate = None
                        if mark_raw:
                            m_dict = json.loads(mark_raw)
                            mark_price = m_dict.get("mark_price")
                            funding_rate = m_dict.get("funding_rate")

                        async with get_db_session() as session:
                            await insert_derivatives_snapshot(session, {
                                "symbol": db_sym,
                                "ts": oi_data["time"],
                                "funding": funding_rate,
                                "mark": mark_price,
                                "open_interest": oi_data["open_interest"],
                                "ls_ratio": ls_ratio,
                            })
                    except Exception as der_err:
                        logger.warning(
                            "derivatives_poll_partial_error", symbol=sym, error=str(der_err)
                        )

            except Exception as exc:
                logger.error("poller_cycle_error", error=str(exc))

            # Sleep 5 minutes
            await asyncio.sleep(300)

    async def _gap_fill_check(self) -> None:
        """Check for missing candles (e.g. after network drop) and fill them."""
        logger.info("running_gap_fill_check")
        now = utc_now()
        async with get_db_session() as session:
            for sym in self.crypto_symbols:
                for tf in self.timeframes:
                    try:
                        latest = await get_latest_candle(session, sym, tf)
                        if latest:
                            diff_seconds = (now - latest.open_time).total_seconds()
                            # If gap is greater than 2 bars
                            thresholds = {"M15": 1800, "H1": 7200, "H4": 28800, "D1": 172800}
                            if diff_seconds > thresholds.get(tf, 1800):
                                logger.warning(
                                    "gap_detected", symbol=sym, tf=tf, gap_seconds=diff_seconds
                                )
                                start_ms = int(latest.open_time.timestamp() * 1000)
                                intv = tf.lower()
                                missing = await self.connector.fetch_klines(
                                    sym,
                                    interval=intv,
                                    start_time=start_ms,
                                    is_futures=True,
                                )
                                closed_missing = [
                                    c for c in missing if c["open_time"] > latest.open_time
                                ]
                                if closed_missing:
                                    await upsert_candles(session, closed_missing)
                                    logger.info(
                                        "gap_filled", symbol=sym, tf=tf, count=len(closed_missing)
                                    )
                    except Exception as e:
                        logger.warning("gap_fill_error", symbol=sym, tf=tf, error=str(e))

    async def _gold_health_monitor(self) -> None:
        """Monitor Gold ticks and trigger automatic failover if primary dies."""
        while self.is_running:
            await asyncio.sleep(10)
            now = time.time()
            elapsed = now - self._last_gold_tick_time

            # If no ticks received for longer than threshold and market is open
            from traderadar.core.time import is_gold_market_open
            if is_gold_market_open(utc_now()) and elapsed > self.gold_manager.switch_after_seconds:
                switched = await self.gold_manager.record_failure(
                    f"Tidak ada data tick Gold selama {int(elapsed)} detik"
                )
                if switched:
                    logger.warning("gold_fallback_switched_restarting_streams")
                    # Restart WebSocket streams with the newly active gold symbol
                    self.connector.stop()

    async def start(self) -> None:
        """Start the entire ingestor loop."""
        self.is_running = True
        logger.info("market_data_ingestor_starting")

        # 1. Register connector callbacks
        self.connector.on_candle_closed = self._on_candle_closed
        self.connector.on_live_bar = self._on_live_bar
        self.connector.on_tick = self._on_tick
        self.connector.on_depth = self._on_depth
        self.connector.on_mark_price = self._on_mark_price

        # 2. Historical Backfill
        try:
            await self.initialize_backfill()
        except Exception as exc:
            logger.warning("initial_backfill_warning", error=str(exc))

        # 3. Launch background poller & gold health monitor
        tasks = [
            asyncio.create_task(self._derivatives_and_sentiment_poller()),
            asyncio.create_task(self._gold_health_monitor()),
        ]

        # 4. Stream loop
        try:
            while self.is_running:
                # Run gap fill
                await self._gap_fill_check()

                # Start WebSocket
                await self.connector.start_combined_stream(
                    futures_symbols=self.all_futures_symbols,
                    timeframes=self.timeframes,
                )
                if self.is_running:
                    await asyncio.sleep(2.0)
        finally:
            for t in tasks:
                t.cancel()
            self.connector.stop()


async def ingestor_service_main() -> None:
    """Entry point for ingestor background service."""
    ingestor = MarketDataIngestor()
    await ingestor.start()


def main() -> None:
    """CLI runner entry point."""
    run_service("ingestor", task_callback=ingestor_service_main)


if __name__ == "__main__":
    main()
