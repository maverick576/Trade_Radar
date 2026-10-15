"""Database connectivity and async session management for PostgreSQL/TimescaleDB."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from traderadar.core.config import get_settings

Base = declarative_base()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create singleton AsyncEngine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.env.DATABASE_URL
        if not db_url:
            raise ValueError("DATABASE_URL belum dikonfigurasi.")
        _engine = create_async_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create async_sessionmaker."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_db() -> bool:
    """Check database liveness by running SELECT 1."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False


async def close_db() -> None:
    """Dispose database engine connections gracefully."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
