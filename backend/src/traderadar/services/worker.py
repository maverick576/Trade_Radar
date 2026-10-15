"""Worker service for background jobs (AI comments, market briefs, backtest)."""

import asyncio
import json
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import select

from traderadar.ai.brief import generate_market_brief
from traderadar.ai.schemas import AIInputPayload
from traderadar.ai.service import AIService
from traderadar.core.config import get_settings
from traderadar.core.db import get_db_session
from traderadar.core.events import STREAM_SIGNALS
from traderadar.core.logging import get_logger
from traderadar.core.models import AICommentRecord, AnalysisRecord, SignalRecord
from traderadar.core.redis import get_redis_client
from traderadar.services.runner import run_service

logger = get_logger("traderadar.worker")


async def ping_job(ctx: dict[str, Any]) -> str:
    """Sample health/test job for arq worker."""
    return "pong"


async def process_market_brief_job(ctx: dict[str, Any], kind: str = "morning") -> dict[str, Any]:
    """Background arq job for Market Brief generation."""
    settings = get_settings()
    redis = get_redis_client()
    ai_service = AIService(settings=settings, redis_client=redis)

    async with get_db_session() as session:
        narrative, brief_rec = await generate_market_brief(
            session=session,
            ai_service=ai_service,
            settings=settings,
            kind=kind,
        )
        await session.commit()
        return {
            "brief_id": brief_rec.id if brief_rec else None,
            "kind": kind,
            "status": "success",
        }


class WorkerSettings:
    """Settings class for arq worker execution."""

    functions = [ping_job, process_market_brief_job]
    max_jobs = 4
    job_timeout = 300

    @classmethod
    def get_redis_settings(cls) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.env.REDIS_URL)


async def process_strong_signal(
    signal_id: int,
    ai_service: AIService,
) -> None:
    """Generate AI technical commentary for a strong signal automatically."""
    async with get_db_session() as session:
        # 1. Fetch signal with analysis and ticket
        stmt = select(SignalRecord).where(SignalRecord.id == signal_id)
        res = await session.execute(stmt)
        sig = res.scalar_one_or_none()
        if not sig or not sig.analysis_id:
            return

        stmt_analysis = select(AnalysisRecord).where(AnalysisRecord.id == sig.analysis_id)
        res_a = await session.execute(stmt_analysis)
        analysis = res_a.scalar_one_or_none()
        if not analysis:
            return

        # Check if already commented
        stmt_check = (
            select(AICommentRecord).where(AICommentRecord.analysis_id == analysis.id).limit(1)
        )
        res_c = await session.execute(stmt_check)
        if res_c.scalar_one_or_none() is not None:
            return

        ticket = sig.ticket
        plan = None
        price = 0.0
        if ticket:
            price = ticket.entry
            plan = {
                "entry": ticket.entry,
                "sl": ticket.sl,
                "tp1": ticket.tp1,
                "tp2": ticket.tp2,
                "atr": ticket.atr,
            }
        else:
            # Fallback to indicators vwap or reference
            for ind in analysis.indicators:
                if "vwap" in ind.get("values", {}):
                    price = float(ind["values"]["vwap"])
                    break

        payload = AIInputPayload(
            symbol=analysis.symbol,
            tf=analysis.tf,
            bar_time=analysis.bar_time.isoformat(),
            price=price or 1.0,
            verdict=analysis.verdict,
            score=analysis.score,
            counts=analysis.counts,
            indicators=analysis.indicators,
            macro=analysis.macro,
            plan=plan,
            htf=analysis.htf,
            strategy_b=analysis.strategy_b,
        )

        resp = await ai_service.generate_comment(
            payload=payload,
            analysis_id=analysis.id,
            session=session,
            is_ondemand=False,
        )
        await session.commit()
        logger.info(
            "auto_ai_comment_generated",
            signal_id=signal_id,
            symbol=analysis.symbol,
            provider=resp.provider,
            latency_ms=resp.latency_ms,
        )


async def consume_signals_stream() -> None:
    """Consume signals stream and trigger AI commentary for strong signals."""
    redis = get_redis_client()
    settings = get_settings()
    ai_service = AIService(settings=settings, redis_client=redis)

    group_name = "worker"
    consumer_name = "worker-1"

    try:
        await redis.xgroup_create(STREAM_SIGNALS, group_name, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            logger.warning("xgroup_create_worker_failed", error=str(exc))

    logger.info("signals_consumer_ready", stream=STREAM_SIGNALS, group=group_name)

    while True:
        try:
            streams = await redis.xreadgroup(
                group_name,
                consumer_name,
                {STREAM_SIGNALS: ">"},
                count=5,
                block=2000,
            )
            if not streams:
                await asyncio.sleep(0.5)
                continue

            for stream_name, messages in streams:
                for msg_id, raw_data in messages:
                    try:
                        raw_bytes = raw_data.get(b"data") or raw_data.get("data")
                        if not raw_bytes:
                            await redis.xack(stream_name, group_name, msg_id)
                            continue

                        evt_dict = json.loads(raw_bytes)
                        verdict = evt_dict.get("verdict", "")
                        signal_id = evt_dict.get("signal_id")

                        # Only automatically trigger AI for strong signals
                        if "STRONG" in verdict and signal_id:
                            await process_strong_signal(int(signal_id), ai_service)

                        await redis.xack(stream_name, group_name, msg_id)
                    except Exception as exc:
                        logger.error(
                            "error_processing_signal_for_ai", msg_id=msg_id, error=str(exc)
                        )
                        await redis.xack(stream_name, group_name, msg_id)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("signals_consumer_loop_error", error=str(exc))
            await asyncio.sleep(2.0)


async def worker_loop() -> None:
    """Worker background routine running signal consumption and background processing."""
    logger.info("worker_service_ready", note="Awaiting AI & backtest background jobs")
    await consume_signals_stream()


def main() -> None:
    """CLI entrypoint."""
    run_service("worker", task_callback=worker_loop)


if __name__ == "__main__":
    main()
