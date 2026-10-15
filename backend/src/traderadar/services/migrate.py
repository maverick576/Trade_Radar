"""Database migration and initial setup service (one-shot)."""

import asyncio
import shutil
import sys
from pathlib import Path

from sqlalchemy import text

from traderadar.core.config import get_settings
from traderadar.core.db import close_db, get_engine
from traderadar.core.logging import get_logger, setup_logging


async def run_migrations() -> None:
    """Run database initializations and seed checks."""
    settings = get_settings()
    setup_logging(log_level=settings.env.LOG_LEVEL, json_format=True)
    logger = get_logger("traderadar.migrate")

    logger.info("migration_started", version=settings.env.APP_VERSION)

    # 1. Initialize settings.yaml from example if missing
    for base in [Path("config"), Path("/app/config"), Path("../config")]:
        example_yaml = base / "settings.example.yaml"
        active_yaml = base / "settings.yaml"
        if example_yaml.exists() and not active_yaml.exists():
            try:
                shutil.copyfile(example_yaml, active_yaml)
                logger.info("copied_settings_example", src=str(example_yaml), dest=str(active_yaml))
            except Exception as e:
                logger.warning("could_not_copy_settings", error=str(e))

    # 2. Check DB and TimescaleDB extension
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            # Enable TimescaleDB extension if available
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            await conn.commit()
            logger.info("timescaledb_extension_verified")
    except Exception as exc:
        logger.error("migration_failed", error=str(exc))
        sys.exit(1)
    finally:
        await close_db()

    logger.info("migration_completed_successfully")


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_migrations())


if __name__ == "__main__":
    main()
