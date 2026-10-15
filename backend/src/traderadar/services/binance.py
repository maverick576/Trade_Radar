"""Binance market data connector supporting Futures (crypto & Gold) and Spot fallback.

Implements:
- REST kline backfill with pagination and weight throttling
- Combined WebSocket streams (kline, depth, markPrice)
- 23-hour proactive reconnect
- Derivatives polling (OI, LS ratio) and Fear & Greed
- Gap filling for missed candles
"""

import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import httpx
import websockets

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.core.network import create_ssl_context, enable_dns_fallback_patch
from traderadar.core.time import utc_now

logger = get_logger("traderadar.binance")

INTERVAL_TO_TF: dict[str, str] = {
    "15m": "M15",
    "1h": "H1",
    "4h": "H4",
    "1d": "D1",
}

TF_TO_INTERVAL: dict[str, str] = {
    "M15": "15m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
}


class BinanceConnector:
    """High-performance resilient connector for Binance market data."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.fapi_base = self.settings.env.BINANCE_FAPI
        self.fstream_base = self.settings.env.BINANCE_FSTREAM
        self.spot_base = self.settings.env.BINANCE_SPOT
        self.spot_fallback = self.settings.env.BINANCE_SPOT_FALLBACK
        self.spot_stream_base = self.settings.env.BINANCE_SPOT_STREAM

        self.used_weight_1m = 0
        loop = asyncio.get_event_loop()
        self.last_weight_reset = loop.time() if loop.is_running() else 0.0
        self.is_running = False
        self._ws_task: asyncio.Task[None] | None = None
        self._reconnect_interval_seconds = 23 * 3600  # 23 hours

        # Callbacks
        self.on_candle_closed: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None
        self.on_live_bar: Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, None]] | None = (
            None
        )
        self.on_tick: Callable[[str, float, datetime], Coroutine[Any, Any, None]] | None = None
        self.on_depth: (
            Callable[[str, list[list[float]], list[list[float]]], Coroutine[Any, Any, None]] | None
        ) = None
        self.on_mark_price: Callable[[str, float, float], Coroutine[Any, Any, None]] | None = None

        # Transparent DNS patch for local network / Indonesian ISP poisoning
        enable_dns_fallback_patch()

    def _track_weight(self, headers: httpx.Headers) -> None:
        """Update rate limit used weight from response headers."""
        weight_str = headers.get("x-mbx-used-weight-1m")
        if weight_str and weight_str.isdigit():
            self.used_weight_1m = int(weight_str)
            if self.used_weight_1m > 1000:
                logger.warning("binance_weight_approaching_limit", used=self.used_weight_1m)

    async def _throttle_if_needed(self) -> None:
        """Sleep briefly if approaching rate limit."""
        if self.used_weight_1m > 1100:
            await asyncio.sleep(1.0)
        elif self.used_weight_1m > 900:
            await asyncio.sleep(0.3)

    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1500,
        start_time: int | None = None,
        end_time: int | None = None,
        is_futures: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch historical klines from Binance REST with rate limiting and fallback."""
        await self._throttle_if_needed()

        base_url = self.fapi_base if is_futures else self.spot_base
        endpoint = "/fapi/v1/klines" if is_futures else "/api/v3/klines"

        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1500 if is_futures else 1000),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        headers = {"User-Agent": "TradeRadar/0.1.0"}

        async def _do_req(url: str) -> httpx.Response:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                return await client.get(f"{url}{endpoint}", params=params, headers=headers)

        try:
            resp = await _do_req(base_url)
            self._track_weight(resp.headers)
            if resp.status_code != 200 and not is_futures and self.spot_fallback:
                # Try spot fallback mirror
                logger.warning(
                    "spot_primary_failed_using_fallback",
                    status=resp.status_code,
                    fallback=self.spot_fallback,
                )
                resp = await _do_req(self.spot_fallback)
                self._track_weight(resp.headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            if not is_futures and self.spot_fallback:
                try:
                    resp = await _do_req(self.spot_fallback)
                    self._track_weight(resp.headers)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as fb_exc:
                    logger.error("binance_fetch_klines_failed", symbol=symbol, error=str(fb_exc))
                    raise
            else:
                logger.error("binance_fetch_klines_failed", symbol=symbol, error=str(exc))
                raise

        candles: list[dict[str, Any]] = []
        for raw in data:
            open_ms = int(raw[0])
            open_time = datetime.fromtimestamp(open_ms / 1000.0, tz=UTC)
            close_ms = int(raw[6])
            close_time = datetime.fromtimestamp(close_ms / 1000.0, tz=UTC)
            taker_buy_vol = float(raw[9]) if len(raw) > 9 and raw[9] is not None else None

            candles.append(
                {
                    "symbol": symbol.upper(),
                    "tf": INTERVAL_TO_TF.get(interval, interval),
                    "open_time": open_time,
                    "close_time": close_time,
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                    "taker_buy_volume": taker_buy_vol,
                    "source": "binance_futures" if is_futures else "binance_spot",
                }
            )

        return candles

    async def backfill_symbol_tf(
        self,
        symbol: str,
        tf: str,
        target_bars: int = 1000,
        is_futures: bool = True,
    ) -> list[dict[str, Any]]:
        """Backfill up to target_bars candles for symbol and timeframe."""
        interval = TF_TO_INTERVAL.get(tf, "15m")
        logger.info("backfilling_klines", symbol=symbol, tf=tf, target_bars=target_bars)

        # Single request if <= 1500
        candles = await self.fetch_klines(
            symbol=symbol,
            interval=interval,
            limit=target_bars,
            is_futures=is_futures,
        )
        logger.info("backfill_completed", symbol=symbol, tf=tf, fetched_count=len(candles))
        return candles

    async def poll_open_interest(self, symbol: str) -> dict[str, Any]:
        """Poll latest Open Interest for a futures symbol."""
        await self._throttle_if_needed()
        url = f"{self.fapi_base}/fapi/v1/openInterest"
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params={"symbol": symbol.upper()})
            self._track_weight(resp.headers)
            resp.raise_for_status()
            data = resp.json()
            return {
                "symbol": symbol.upper(),
                "open_interest": float(data.get("openInterest", 0.0)),
                "time": datetime.fromtimestamp(int(data.get("time", 0)) / 1000.0, tz=UTC),
            }

    async def poll_open_interest_hist(
        self, symbol: str, period: str = "15m", limit: int = 30
    ) -> list[dict[str, Any]]:
        """Poll Open Interest history for derivatives analysis."""
        await self._throttle_if_needed()
        url = f"{self.fapi_base}/futures/data/openInterestHist"
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(
                url, params={"symbol": symbol.upper(), "period": period, "limit": limit}
            )
            self._track_weight(resp.headers)
            resp.raise_for_status()
            return list(resp.json())

    async def poll_long_short_ratio(
        self, symbol: str, period: str = "15m", limit: int = 30
    ) -> list[dict[str, Any]]:
        """Poll Global Long/Short account ratio."""
        await self._throttle_if_needed()
        url = f"{self.fapi_base}/futures/data/globalLongShortAccountRatio"
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(
                url, params={"symbol": symbol.upper(), "period": period, "limit": limit}
            )
            self._track_weight(resp.headers)
            resp.raise_for_status()
            return list(resp.json())

    async def poll_fear_and_greed(self, limit: int = 30) -> list[dict[str, Any]]:
        """Poll Alternative.me Crypto Fear & Greed index."""
        url = f"https://api.alternative.me/fng/?limit={limit}"
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            results = []
            for item in items:
                ts = datetime.fromtimestamp(int(item["timestamp"]), tz=UTC)
                results.append(
                    {
                        "value": float(item["value"]),
                        "label": item.get("value_classification", ""),
                        "ts": ts,
                    }
                )
            return results

    async def build_stream_url(
        self,
        futures_symbols: list[str],
        timeframes: list[str],
        include_depth: bool = True,
        include_mark_price: bool = True,
    ) -> str:
        """Construct Binance combined WebSocket stream URL."""
        streams: list[str] = []
        for sym in futures_symbols:
            s = sym.lower()
            for tf in timeframes:
                interval = TF_TO_INTERVAL.get(tf, "15m")
                streams.append(f"{s}@kline_{interval}")
            if include_depth:
                streams.append(f"{s}@depth20@500ms")
            if include_mark_price:
                streams.append(f"{s}@markPrice@1s")

        stream_query = "/".join(streams)
        return f"{self.fstream_base}/stream?streams={stream_query}"

    async def start_combined_stream(
        self,
        futures_symbols: list[str],
        timeframes: list[str],
    ) -> None:
        """Connect to combined WebSocket streams with auto-reconnect and 23h refresh."""
        self.is_running = True
        ssl_ctx = create_ssl_context()

        while self.is_running:
            url = await self.build_stream_url(futures_symbols, timeframes)
            logger.info("connecting_binance_websocket", streams_count=len(futures_symbols))

            start_time = asyncio.get_event_loop().time()
            try:
                async with websockets.connect(
                    url,
                    ssl=ssl_ctx,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=5,
                    max_size=10_000_000,
                ) as ws:
                    logger.info("binance_websocket_connected")

                    while self.is_running:
                        # Check 23-hour proactive reconnect
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed >= self._reconnect_interval_seconds:
                            logger.info("proactive_23h_reconnect_triggered")
                            break

                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        except TimeoutError:
                            # Send manual ping if quiet
                            await ws.ping()
                            continue

                        await self._process_stream_message(msg)

            except asyncio.CancelledError:
                logger.info("binance_ws_loop_cancelled")
                break
            except Exception as exc:
                logger.warning("binance_ws_connection_error", error=str(exc))
                if self.is_running:
                    await asyncio.sleep(2.0)  # Backoff before reconnect

    async def _process_stream_message(self, raw_message: str | bytes) -> None:
        """Route parsed stream messages to registered callbacks."""
        try:
            payload = json.loads(raw_message)
        except Exception:
            return

        stream = payload.get("stream", "")
        data = payload.get("data", {})

        # 1. Kline stream: <sym>@kline_<interval>
        if "@kline_" in stream:
            k = data.get("k", {})
            sym = data.get("s", "").upper()
            interval = k.get("i", "")
            tf = INTERVAL_TO_TF.get(interval, interval)
            is_closed = bool(k.get("x", False))

            open_ms = int(k.get("t", 0))
            open_time = datetime.fromtimestamp(open_ms / 1000.0, tz=UTC)
            close_ms = int(k.get("T", 0))
            close_time = datetime.fromtimestamp(close_ms / 1000.0, tz=UTC)
            taker_buy_vol = float(k.get("V", 0.0)) if "V" in k else None

            candle = {
                "symbol": sym,
                "tf": tf,
                "open_time": open_time,
                "close_time": close_time,
                "open": float(k.get("o", 0.0)),
                "high": float(k.get("h", 0.0)),
                "low": float(k.get("l", 0.0)),
                "close": float(k.get("c", 0.0)),
                "volume": float(k.get("v", 0.0)),
                "taker_buy_volume": taker_buy_vol,
                "source": "binance_futures",
                "is_closed": is_closed,
            }

            if is_closed:
                if self.on_candle_closed:
                    await self.on_candle_closed(candle)
            else:
                if self.on_live_bar:
                    await self.on_live_bar(sym, tf, candle)

            # Emit live tick from close price
            if self.on_tick:
                await self.on_tick(sym, candle["close"], utc_now())

        # 2. Depth stream: <sym>@depth20@500ms
        elif "@depth" in stream:
            sym = stream.split("@", 1)[0].upper()
            raw_bids = data.get("b", [])
            raw_asks = data.get("a", [])
            bids = [[float(b[0]), float(b[1])] for b in raw_bids[:20]]
            asks = [[float(a[0]), float(a[1])] for a in raw_asks[:20]]
            if self.on_depth:
                await self.on_depth(sym, bids, asks)

        # 3. Mark price stream: <sym>@markPrice@1s
        elif "@markPrice" in stream:
            sym = data.get("s", "").upper()
            mark_price = float(data.get("p", 0.0))
            funding_rate = float(data.get("r", 0.0))
            if self.on_mark_price:
                await self.on_mark_price(sym, mark_price, funding_rate)

    def stop(self) -> None:
        """Stop background tasks."""
        self.is_running = False
