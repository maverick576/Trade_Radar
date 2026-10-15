"""Signal and confluence analysis engine service."""

import asyncio

from traderadar.core.logging import get_logger
from traderadar.services.runner import run_service

logger = get_logger("traderadar.engine")


async def engine_loop() -> None:
    """Engine background routine."""
    logger.info("engine_worker_ready", note="Awaiting candles.closed event stream")
    while True:
        # Placeholder loop until Fase 4 confluence evaluation activation
        await asyncio.sleep(60)


def main() -> None:
    """CLI entrypoint."""
    run_service("engine", task_callback=engine_loop)


if __name__ == "__main__":
    main()
