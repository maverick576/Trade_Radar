"""Confluence analysis engine service consuming candles.closed events."""

import asyncio
import json
from typing import Any

import pandas as pd
from redis.asyncio import Redis

from traderadar.core.db import get_db_session
from traderadar.core.events import (
    CHANNEL_UI_EVENTS,
    STREAM_CANDLES_CLOSED,
    STREAM_SIGNALS,
    CandleClosedEvent,
    SignalEvent,
    UIEvent,
)
from traderadar.core.logging import get_logger
from traderadar.core.redis import get_redis
from traderadar.core.time import utc_now
from traderadar.engine.indicators.base import MarketContext
from traderadar.engine.strategies.konfluensi10 import ConfluencePipeline
from traderadar.services.analysis_store import get_latest_analysis, save_analysis_and_signals
from traderadar.services.candle_store import get_candles
from traderadar.services.runner import run_service

logger = get_logger("traderadar.engine")


async def build_market_context(redis_client: Redis, symbol: str) -> MarketContext:
    """Fetch live market context (derivatives snapshot, sentiment) from Redis."""
    is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
    ctx = MarketContext(is_gold=is_gold)

    try:
        deriv_raw = await redis_client.get(f"derivatives:{symbol.upper()}")
        if deriv_raw:
            deriv = json.loads(deriv_raw)
            ctx.funding_rate = deriv.get("funding")
            ctx.open_interest_current = deriv.get("open_interest")
            ctx.open_interest_4h_ago = deriv.get("open_interest_4h_ago")
            ctx.long_short_ratio = deriv.get("ls_ratio")

        fng_val = await redis_client.get("sentiment:fng")
        if fng_val:
            ctx.fear_and_greed = int(fng_val)
    except Exception as e:
        logger.warning("market_context_fetch_failed", symbol=symbol, error=str(e))

    return ctx


async def process_closed_candle(
    redis_client: Redis,
    pipeline: ConfluencePipeline,
    event: CandleClosedEvent,
) -> None:
    """Run confluence analysis and emit signals for closed M15 candle."""
    symbol = event.symbol.upper()
    tf = event.tf.upper()

    # We evaluate full 10-indicator confluence on entry timeframe M15
    if tf != "M15":
        return

    logger.info("processing_m15_confluence", symbol=symbol, bar_time=event.bar_time.isoformat())

    async with get_db_session() as session:
        # 1. Fetch candles for M15, H1, H4, D1
        m15_rows = await get_candles(session, symbol, "M15", limit=300)
        h1_rows = await get_candles(session, symbol, "H1", limit=100)
        h4_rows = await get_candles(session, symbol, "H4", limit=100)
        d1_rows = await get_candles(session, symbol, "D1", limit=50)

        if len(m15_rows) < 20:
            logger.warning("insufficient_m15_candles", symbol=symbol, count=len(m15_rows))
            return

        def rows_to_df(rows: list[Any]) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {
                        "open_time": r.open_time,
                        "open": r.open,
                        "high": r.high,
                        "low": r.low,
                        "close": r.close,
                        "volume": r.volume,
                        "taker_buy_volume": r.taker_buy_volume,
                    }
                    for r in rows
                ]
            )

        df_m15 = rows_to_df(m15_rows)
        df_h1 = rows_to_df(h1_rows) if h1_rows else None
        df_h4 = rows_to_df(h4_rows) if h4_rows else None
        df_d1 = rows_to_df(d1_rows) if d1_rows else None

        # 2. Get previous analysis for cooldown detection
        prev_analysis = await get_latest_analysis(session, symbol, "M15")
        prev_side = None
        prev_bars_ago = None
        if prev_analysis is not None:
            if "LONG" in prev_analysis.verdict:
                prev_side = "LONG"
            elif "SHORT" in prev_analysis.verdict:
                prev_side = "SHORT"
            # Calculate bars ago approximately
            diff_sec = (event.bar_time - prev_analysis.bar_time).total_seconds()
            prev_bars_ago = int(diff_sec // 900)

        # 3. Build Market Context
        context = await build_market_context(redis_client, symbol)

        # 4. Execute Analysis Pipeline
        analysis, signals = pipeline.run_analysis(
            symbol=symbol,
            tf=tf,
            source=event.source,
            df_m15=df_m15,
            df_h1=df_h1,
            df_h4=df_h4,
            df_d1=df_d1,
            context=context,
            previous_signal_side=prev_side,
            previous_signal_bars_ago=prev_bars_ago,
        )

        # 5. Persist to Database
        record, saved_signals = await save_analysis_and_signals(session, analysis, signals)
        logger.info(
            "analysis_persisted",
            symbol=symbol,
            score=analysis.score,
            verdict=analysis.verdict,
            signals_count=len(saved_signals),
        )

    # 6. Cache latest analysis in Redis for immediate UI access
    analysis_dict = analysis.model_dump(mode="json")
    await redis_client.set(f"analysis:latest:{symbol}:{tf}", json.dumps(analysis_dict))

    # 7. Publish UI Event via PubSub
    ui_evt = UIEvent(
        type="analysis",
        data={
            "symbol": symbol,
            "tf": tf,
            "analysis": analysis_dict,
        },
        ts=utc_now(),
    )
    await redis_client.publish(CHANNEL_UI_EVENTS, ui_evt.model_dump_json())

    # 8. Emit to Redis Stream `signals` if strong signals generated
    for sig in saved_signals:
        sig_evt = SignalEvent(
            event_id=f"sig:{sig.id}",
            signal_id=sig.id,
            ticket_id=None,
            strategy=sig.strategy,
            symbol=sig.symbol,
            tf=sig.tf,
            side="LONG" if sig.side == "LONG" else "SHORT",
            verdict=sig.verdict,  # type: ignore[arg-type]
            bar_time=sig.bar_time,
            created_at=sig.created_at,
        )
        await redis_client.xadd(
            STREAM_SIGNALS,
            {"data": sig_evt.model_dump_json()},
            maxlen=5000,
        )

        # Also send UI signal notification
        sig_ui_evt = UIEvent(
            type="signal",
            data={
                "signal_id": sig.id,
                "symbol": sig.symbol,
                "strategy": sig.strategy,
                "side": sig.side,
                "verdict": sig.verdict,
                "status": sig.status,
                "blocked_by": sig.blocked_by,
                "bar_time": sig.bar_time.isoformat(),
            },
            ts=utc_now(),
        )
        await redis_client.publish(CHANNEL_UI_EVENTS, sig_ui_evt.model_dump_json())


async def engine_loop() -> None:
    """Engine background routine consuming candles.closed events."""
    redis_client = get_redis()
    pipeline = ConfluencePipeline()

    group_name = "engine"
    consumer_name = "engine_worker_1"

    # Ensure stream and consumer group exist
    try:
        await redis_client.xgroup_create(
            STREAM_CANDLES_CLOSED,
            group_name,
            id="0",
            mkstream=True,
        )
        logger.info("consumer_group_created", stream=STREAM_CANDLES_CLOSED, group=group_name)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            logger.warning("xgroup_create_notice", error=str(e))

    logger.info("engine_service_ready", stream=STREAM_CANDLES_CLOSED)

    while True:
        try:
            # Read new events from consumer group
            entries = await redis_client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={STREAM_CANDLES_CLOSED: ">"},
                count=10,
                block=2000,
            )

            if not entries:
                continue

            for stream_name, messages in entries:
                for msg_id, data in messages:
                    try:
                        raw_payload = data.get("data") or data.get(b"data")
                        if raw_payload:
                            if isinstance(raw_payload, bytes):
                                raw_payload = raw_payload.decode("utf-8")
                            parsed = json.loads(raw_payload)
                            event = CandleClosedEvent(**parsed)
                            await process_closed_candle(redis_client, pipeline, event)

                        # Acknowledge processed message
                        await redis_client.xack(stream_name, group_name, msg_id)
                    except Exception as exc:
                        logger.error("candle_event_process_failed", msg_id=msg_id, error=str(exc))
                        # Still ack to prevent poison pills
                        await redis_client.xack(stream_name, group_name, msg_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("engine_loop_error", error=str(e))
            await asyncio.sleep(2)


def main() -> None:
    """CLI entrypoint."""
    run_service("engine", task_callback=engine_loop)


if __name__ == "__main__":
    main()
