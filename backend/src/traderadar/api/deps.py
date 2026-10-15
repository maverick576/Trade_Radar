"""Dependencies for FastAPI routes."""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.core.config import Settings, get_settings
from traderadar.core.db import get_db_session
from traderadar.core.redis import get_redis


def get_current_settings() -> Settings:
    """Dependency for application settings."""
    return get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session."""
    async with get_db_session() as session:
        yield session


def get_redis_client() -> Redis:
    """Dependency for Redis client."""
    return get_redis()
