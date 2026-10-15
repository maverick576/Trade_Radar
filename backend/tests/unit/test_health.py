"""Unit tests for health endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient) -> None:
    """Test /api/health response format."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "time" in data


@pytest.mark.asyncio
async def test_health_root_alias(client: AsyncClient) -> None:
    """Test root /health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
