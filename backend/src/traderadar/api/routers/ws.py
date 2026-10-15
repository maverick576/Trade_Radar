"""WebSocket router (/ws) streaming live ticks, candles, gold source events, and status."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.core.redis import get_redis
from traderadar.core.security import decode_access_token
from traderadar.core.time import to_iso_utc, utc_now

logger = get_logger("traderadar.ws")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Full-duplex WebSocket streaming market data and events."""
    await websocket.accept()

    settings = get_settings()
    # 1. Authenticate via cookie or query param
    token = websocket.cookies.get("traderadar_access") or websocket.cookies.get("access_token")
    if not token:
        token = websocket.query_params.get("token")

    if not token and settings.env.APP_VERSION != "dev":
        logger.warning("ws_auth_failed_missing_token")
        await websocket.close(code=1008)
        return

    if token:
        try:
            decode_access_token(token)
        except Exception as exc:
            if settings.env.APP_VERSION != "dev":
                logger.warning("ws_auth_invalid_token", error=str(exc))
                await websocket.close(code=1008)
                return

    # Client subscription state
    subscribed_symbols: set[str] = {item.symbol.upper() for item in settings.app.watchlist} | {
        "XAUUSD"
    }
    subscribed_tfs: set[str] = {"M15", "H1", "H4", "D1"}

    redis_client = await get_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("ui.events")

    # Send initial connected status message
    await websocket.send_text(
        json.dumps(
            {
                "type": "status",
                "data": {
                    "connected": True,
                    "symbols": list(subscribed_symbols),
                    "tfs": list(subscribed_tfs),
                    "server_time": to_iso_utc(utc_now()),
                },
            }
        )
    )

    async def _redis_listener() -> None:
        """Listen to Redis PubSub and forward matched events to WebSocket client."""
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    raw_data = msg.get("data")
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")

                    try:
                        event = json.loads(raw_data)
                        ev_type = event.get("type")
                        data = event.get("data", {})

                        # Filter ticks
                        if ev_type == "tick":
                            sym = data.get("symbol", "").upper()
                            if sym in subscribed_symbols:
                                await websocket.send_text(raw_data)

                        # Filter candles / live bars
                        elif ev_type in ("candle", "live_bar"):
                            sym = data.get("symbol", "").upper()
                            tf = data.get("tf", "").upper()
                            if (not subscribed_symbols or sym in subscribed_symbols) and (
                                not subscribed_tfs or tf in subscribed_tfs
                            ):
                                await websocket.send_text(raw_data)

                        # System / gold source / status events pass through
                        else:
                            await websocket.send_text(raw_data)

                    except Exception as parse_err:
                        logger.debug("ws_event_forward_error", error=str(parse_err))

                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass

    redis_task = asyncio.create_task(_redis_listener())

    try:
        while True:
            text = await websocket.receive_text()
            try:
                cmd = json.loads(text)
                cmd_type = cmd.get("type")

                if cmd_type == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "ts": to_iso_utc(utc_now())})
                    )

                elif cmd_type == "subscribe":
                    syms = cmd.get("symbols", [])
                    tfs = cmd.get("tfs", [])
                    if syms:
                        subscribed_symbols = {s.upper() for s in syms}
                    if tfs:
                        subscribed_tfs = {t.upper() for t in tfs}

                    logger.debug(
                        "ws_client_subscribed",
                        symbols=list(subscribed_symbols),
                        tfs=list(subscribed_tfs),
                    )
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "subscribed",
                                "data": {
                                    "symbols": list(subscribed_symbols),
                                    "tfs": list(subscribed_tfs),
                                },
                            }
                        )
                    )
            except Exception as e:
                logger.warning("ws_command_error", error=str(e))

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected")
    finally:
        redis_task.cancel()
        await pubsub.unsubscribe("ui.events")
        await pubsub.close()
