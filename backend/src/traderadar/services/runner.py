"""Generic service runner providing structured logging, periodic heartbeats, and signal handling."""

import asyncio
import signal
import time
from collections.abc import Callable, Coroutine
from typing import Any

from traderadar.core.config import get_settings
from traderadar.core.db import close_db
from traderadar.core.logging import get_logger, setup_logging
from traderadar.core.redis import close_redis, set_heartbeat
from traderadar.core.time import to_iso_utc, utc_now


class ServiceRunner:
    """Manages service lifecycle, heartbeat dispatch, and graceful shutdown."""

    def __init__(
        self,
        service_name: str,
        task_callback: Callable[[], Coroutine[Any, Any, None]] | None = None,
        heartbeat_interval: float = 10.0,
    ) -> None:
        self.service_name = service_name
        self.task_callback = task_callback
        self.heartbeat_interval = heartbeat_interval
        self.is_running = False
        self.start_time: float = 0.0
        self.settings = get_settings()
        self.logger = get_logger(f"traderadar.{service_name}")

    async def _heartbeat_loop(self) -> None:
        """Continuously update service status in Redis."""
        while self.is_running:
            uptime = time.time() - self.start_time
            payload = {
                "service": self.service_name,
                "version": self.settings.env.APP_VERSION,
                "status": "healthy",
                "ts": to_iso_utc(utc_now()),
                "uptime_seconds": round(uptime, 1),
            }
            try:
                await set_heartbeat(self.service_name, payload, ttl_seconds=30)
            except Exception as exc:
                self.logger.warning("heartbeat_failed", error=str(exc))

            await asyncio.sleep(self.heartbeat_interval)

    async def start(self) -> None:
        """Run service and monitor signals."""
        setup_logging(log_level=self.settings.env.LOG_LEVEL, json_format=True)
        self.logger.info("service_starting", service=self.service_name)
        self.is_running = True
        self.start_time = time.time()

        # Register OS signal handlers if supported (UNIX/Linux containers)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                # Signal handlers not implemented on Windows event loop
                pass

        # Initial heartbeat
        await set_heartbeat(
            self.service_name,
            {
                "service": self.service_name,
                "version": self.settings.env.APP_VERSION,
                "status": "healthy",
                "ts": to_iso_utc(utc_now()),
                "uptime_seconds": 0.0,
            },
        )

        tasks = [asyncio.create_task(self._heartbeat_loop())]

        if self.task_callback:
            tasks.append(asyncio.create_task(self.task_callback()))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("service_tasks_cancelled")
        finally:
            await self._cleanup()

    def stop(self) -> None:
        """Trigger shutdown."""
        self.logger.info("service_stopping", service=self.service_name)
        self.is_running = False

    async def _cleanup(self) -> None:
        """Release resources on termination."""
        self.logger.info("service_cleanup", service=self.service_name)
        await close_db()
        await close_redis()
        self.logger.info("service_stopped", service=self.service_name)


def run_service(
    service_name: str,
    task_callback: Callable[[], Coroutine[Any, Any, None]] | None = None,
) -> None:
    """Synchronous entry point that sets up asyncio loop and runs the service."""
    runner = ServiceRunner(service_name=service_name, task_callback=task_callback)
    try:
        asyncio.run(runner.start())
    except (KeyboardInterrupt, SystemExit):
        pass
