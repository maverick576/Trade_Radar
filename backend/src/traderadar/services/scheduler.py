"""Scheduler service for recurring cron jobs (Market Brief, backups, news refresh)."""

import asyncio

from arq.connections import RedisSettings

from traderadar.ai.brief import generate_market_brief
from traderadar.ai.service import AIService
from traderadar.core.config import get_settings
from traderadar.core.db import get_db_session
from traderadar.core.events import CHANNEL_UI_EVENTS, UIEvent
from traderadar.core.logging import get_logger
from traderadar.core.redis import get_redis_client
from traderadar.core.time import to_wib, utc_now
from traderadar.services.runner import run_service

logger = get_logger("traderadar.scheduler")


class SchedulerSettings:
    """Settings class for arq cron scheduler execution."""

    @classmethod
    def get_redis_settings(cls) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.env.REDIS_URL)


async def scheduler_loop() -> None:
    """Scheduler background routine checking time triggers (Brief, backup, recap)."""
    settings = get_settings()
    redis = get_redis_client()
    ai_service = AIService(settings=settings, redis_client=redis)

    logger.info(
        "scheduler_service_ready",
        brief_morning=settings.app.schedule.brief_morning,
        brief_midday=settings.app.schedule.brief_midday,
    )

    last_morning_date: str | None = None
    last_midday_date: str | None = None
    last_recap_date: str | None = None

    while True:
        try:
            now_utc = utc_now()
            now_wib = to_wib(now_utc)
            current_date = now_wib.strftime("%Y-%m-%d")
            current_hm = now_wib.strftime("%H:%M")

            morning_target = settings.app.schedule.brief_morning or "06:45"
            midday_target = settings.app.schedule.brief_midday

            # 1. Check Morning Brief
            if current_hm == morning_target and last_morning_date != current_date:
                logger.info("triggering_scheduled_morning_brief", time_wib=current_hm)
                last_morning_date = current_date
                try:
                    async with get_db_session() as session:
                        narrative, brief_rec = await generate_market_brief(
                            session=session,
                            ai_service=ai_service,
                            settings=settings,
                            kind="morning",
                        )
                        await session.commit()
                        if brief_rec:
                            evt = UIEvent(
                                type="brief",
                                data={
                                    "id": brief_rec.id,
                                    "kind": "morning",
                                    "payload": brief_rec.payload,
                                    "narrative": brief_rec.narrative,
                                },
                                ts=utc_now(),
                            )
                            await redis.publish(CHANNEL_UI_EVENTS, evt.model_dump_json())
                        logger.info(
                            "scheduled_morning_brief_completed",
                            brief_id=brief_rec.id if brief_rec else None,
                        )
                except Exception as exc:
                    logger.error("scheduled_morning_brief_failed", error=str(exc))

            # 2. Check Midday Brief (if configured)
            if midday_target and current_hm == midday_target and last_midday_date != current_date:
                logger.info("triggering_scheduled_midday_brief", time_wib=current_hm)
                last_midday_date = current_date
                try:
                    async with get_db_session() as session:
                        narrative, brief_rec = await generate_market_brief(
                            session=session,
                            ai_service=ai_service,
                            settings=settings,
                            kind="midday",
                        )
                        await session.commit()
                        if brief_rec:
                            evt = UIEvent(
                                type="brief",
                                data={
                                    "id": brief_rec.id,
                                    "kind": "midday",
                                    "payload": brief_rec.payload,
                                    "narrative": brief_rec.narrative,
                                },
                                ts=utc_now(),
                            )
                            await redis.publish(CHANNEL_UI_EVENTS, evt.model_dump_json())
                        logger.info(
                            "scheduled_midday_brief_completed",
                            brief_id=brief_rec.id if brief_rec else None,
                        )
                except Exception as exc:
                    logger.error("scheduled_midday_brief_failed", error=str(exc))

            # 3. Check Daily Recap 22:00 WIB
            recap_target = settings.app.schedule.daily_recap or "22:00"
            if current_hm == recap_target and last_recap_date != current_date:
                logger.info("triggering_scheduled_daily_recap", time_wib=current_hm)
                last_recap_date = current_date
                try:
                    recap_evt = UIEvent(
                        type="daily_recap",
                        data={"date": current_date},
                        ts=utc_now(),
                    )
                    await redis.publish(CHANNEL_UI_EVENTS, recap_evt.model_dump_json())
                    logger.info("scheduled_daily_recap_published", date=current_date)
                except Exception as exc:
                    logger.error("scheduled_daily_recap_failed", error=str(exc))

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("scheduler_loop_error", error=str(exc))

        await asyncio.sleep(20)


def main() -> None:
    """CLI entrypoint."""
    run_service("scheduler", task_callback=scheduler_loop)


if __name__ == "__main__":
    main()
