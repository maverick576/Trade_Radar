"""Market data ingestor service (Binance WebSocket streams, REST pollers)."""

import asyncio

from traderadar.core.logging import get_logger
from traderadar.services.runner import run_service

logger = get_logger("traderadar.ingestor")


async def ingestor_loop() -> None:
    """Ingestor background routine."""
    logger.info("ingestor_worker_ready", note="Awaiting market data pipeline configuration")
    while True:
        # Placeholder loop until Fase 2 Binance pipeline activation
        await asyncio.sleep(60)


def main() -> None:
    """CLI entrypoint."""
    run_service("ingestor", task_callback=ingestor_loop)


if __name__ == "__main__":
    main()
