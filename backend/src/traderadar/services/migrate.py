"""Database migration and initial setup service (one-shot)."""

import asyncio
import shutil
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select, text

from alembic import command
from traderadar.core.config import get_settings
from traderadar.core.db import close_db, get_db_session, get_engine
from traderadar.core.logging import get_logger, setup_logging
from traderadar.core.models import AuditLog, User
from traderadar.core.security import hash_password


async def run_migrations() -> None:
    """Run database initializations, alembic migrations, and admin seeding."""
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
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            await conn.execute(
                text(
                    "DO $$ BEGIN "
                    "IF EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'alembic_version') THEN "
                    "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128); "
                    "END IF; END $$;"
                )
            )
            await conn.commit()
            logger.info("timescaledb_extension_verified")
    except Exception as exc:
        logger.error("timescaledb_extension_failed", error=str(exc))
        sys.exit(1)

    # 3. Find and run Alembic migrations (in separate thread to avoid event loop collision)
    alembic_ini_path: Path | None = None
    for p in [Path("alembic.ini"), Path("/app/alembic.ini"), Path("backend/alembic.ini")]:
        if p.exists() and p.is_file():
            alembic_ini_path = p
            break

    if not alembic_ini_path:
        logger.error("alembic_ini_not_found")
        sys.exit(1)

    logger.info("running_alembic_upgrade", config=str(alembic_ini_path))
    try:
        alembic_cfg = Config(str(alembic_ini_path))
        # Ensure script_location is absolute or correct relative to alembic.ini
        if not alembic_cfg.get_main_option("script_location"):
            alembic_cfg.set_main_option("script_location", str(alembic_ini_path.parent / "alembic"))
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("alembic_upgrade_completed")
    except Exception as exc:
        logger.error("alembic_upgrade_failed", error=str(exc))
        sys.exit(1)

    # 4. Seed admin user from .env
    admin_email = settings.env.ADMIN_EMAIL.strip().lower()
    admin_password = settings.env.ADMIN_PASSWORD
    if admin_email and admin_password:
        try:
            async with get_db_session() as session:
                stmt = select(User).where(User.email == admin_email)
                res = await session.execute(stmt)
                user = res.scalar_one_or_none()
                if user is None:
                    user = User(
                        email=admin_email,
                        password_hash=hash_password(admin_password),
                    )
                    session.add(user)
                    await session.flush()

                    audit = AuditLog(
                        user_id=user.id,
                        action="admin_seeded",
                        detail={"email": admin_email},
                        ip="127.0.0.1",
                    )
                    session.add(audit)
                    logger.info("admin_user_created", email=admin_email)
                else:
                    logger.info("admin_user_already_exists", email=admin_email)
        except Exception as exc:
            logger.error("admin_seed_failed", error=str(exc))
            sys.exit(1)
    else:
        logger.warning("admin_credentials_not_provided_in_env")

    await close_db()
    logger.info("migration_completed_successfully")


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_migrations())


if __name__ == "__main__":
    main()
