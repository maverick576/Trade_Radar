"""Pytest fixtures for unit and integration testing."""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from traderadar.api.app import app
from traderadar.core.config import get_settings


@pytest_asyncio.fixture(autouse=True)
def override_env() -> None:
    """Ensure test environment does not attempt external production connections."""
    os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-chars-long"
    os.environ["APP_VERSION"] = "test"
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://traderadar:test@localhost:5432/traderadar_test"
    )
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test client for FastAPI routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
