"""Integration tests for authentication, authorization gatekeeper, CSRF, and TOTP API."""

from collections.abc import AsyncGenerator
from typing import Any

import pyotp
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from traderadar.api.app import app
from traderadar.api.deps import get_db, get_redis_client
from traderadar.core.models import Base, User
from traderadar.core.security import hash_password
from traderadar.core.time import utc_now


class FakeRedisPipeline:
    """Mock Redis pipeline for rate limiting tests."""

    def __init__(self, storage: dict[str, Any]) -> None:
        self.storage = storage
        self.ops: list[tuple[str, Any]] = []

    def incr(self, key: str) -> "FakeRedisPipeline":
        self.ops.append(("incr", key))
        return self

    def expire(self, key: str, seconds: int) -> "FakeRedisPipeline":
        self.ops.append(("expire", (key, seconds)))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, val in self.ops:
            if op == "incr":
                cur = int(self.storage.get(val, 0)) + 1
                self.storage[val] = str(cur)
                results.append(cur)
            elif op == "expire":
                results.append(True)
        return results


class FakeRedis:
    """Mock Redis instance."""

    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def set(self, key: str, val: str, *args: Any, **kwargs: Any) -> bool:
        self.storage[key] = str(val)
        return True

    async def ttl(self, key: str) -> int:
        return 900

    async def delete(self, key: str) -> int:
        return 1 if self.storage.pop(key, None) is not None else 0

    def pipeline(self) -> FakeRedisPipeline:
        return FakeRedisPipeline(self.storage)


@pytest_asyncio.fixture
async def auth_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client with mocked in-memory database and redis dependencies."""
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Seed test admin user
    async with session_maker() as session:
        admin = User(
            email="admin@example.com",
            password_hash=hash_password("AdminPassword123!"),
            totp_secret=None,
            created_at=utc_now(),
        )
        session.add(admin)
        await session.commit()

    fake_redis = FakeRedis()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_redis() -> FakeRedis:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_gatekeeper_blocks_unauthenticated_api(auth_client: AsyncClient) -> None:
    # Protected endpoint without login must return 401
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_public_health_accessible_without_auth(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_invalid_credentials(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_rate_limiting(auth_client: AsyncClient) -> None:
    # 5 failed attempts
    for _ in range(5):
        resp = await auth_client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401

    # 6th attempt must trigger 429
    resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_login_success_and_cookie_flow(auth_client: AsyncClient) -> None:
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["requires_2fa"] is False
    assert body["user"]["email"] == "admin@example.com"
    csrf_token = body["csrf_token"]
    assert csrf_token is not None

    cookies = login_resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    assert "traderadar_csrf" in cookies

    # Now call /api/auth/me using authenticated client cookies
    me_resp = await auth_client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_csrf_validation_on_state_mutating_request(auth_client: AsyncClient) -> None:
    # 1. Login
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert login_resp.status_code == 200

    # 2. Try changing password without X-CSRF-Token header -> 403
    pwd_resp = await auth_client.put(
        "/api/auth/password",
        json={"old_password": "AdminPassword123!", "new_password": "NewSecretPassword123!"},
    )
    assert pwd_resp.status_code == 403
    assert pwd_resp.json()["error"]["code"] == "CSRF_ERROR"

    # 3. Supply matching X-CSRF-Token header -> 200
    csrf_token = login_resp.json()["csrf_token"]
    pwd_resp_ok = await auth_client.put(
        "/api/auth/password",
        json={"old_password": "AdminPassword123!", "new_password": "NewSecretPassword123!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert pwd_resp_ok.status_code == 200
    assert "berhasil diperbarui" in pwd_resp_ok.json()["message"]


@pytest.mark.asyncio
async def test_session_refresh_and_logout(auth_client: AsyncClient) -> None:
    # 1. Login
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert login_resp.status_code == 200

    # 2. Refresh session
    refresh_resp = await auth_client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.cookies

    # 3. Logout
    logout_resp = await auth_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # 4. Access after logout -> 401
    me_resp = await auth_client.get("/api/auth/me")
    assert me_resp.status_code == 401


@pytest.mark.asyncio
async def test_totp_2fa_full_lifecycle(auth_client: AsyncClient) -> None:
    # 1. Login initial admin
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 2. Setup TOTP
    setup_resp = await auth_client.post(
        "/api/auth/totp/setup",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    secret = setup_data["secret"]
    assert "otpauth_url" in setup_data

    # 3. Verify and activate TOTP
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    verify_resp = await auth_client.post(
        "/api/auth/totp/verify",
        json={"secret": secret, "code": valid_code},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert verify_resp.status_code == 200
    assert "berhasil diaktifkan" in verify_resp.json()["message"]

    # 4. Logout
    await auth_client.post("/api/auth/logout")

    # 5. Login without TOTP code -> requires_2fa=True
    login_step1 = await auth_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert login_step1.status_code == 200
    assert login_step1.json()["requires_2fa"] is True

    # 6. Login with invalid TOTP code -> 401
    login_step2_bad = await auth_client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "AdminPassword123!",
            "totp_code": "000000",
        },
    )
    assert login_step2_bad.status_code == 401

    # 7. Login with valid TOTP code -> 200
    login_step2_ok = await auth_client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "AdminPassword123!",
            "totp_code": totp.now(),
        },
    )
    assert login_step2_ok.status_code == 200
    assert login_step2_ok.json()["requires_2fa"] is False
    csrf2 = login_step2_ok.json()["csrf_token"]

    # 8. Disable TOTP
    disable_resp = await auth_client.post(
        "/api/auth/totp/disable",
        json={"password": "AdminPassword123!", "code": totp.now()},
        headers={"X-CSRF-Token": csrf2},
    )
    assert disable_resp.status_code == 200
    assert "dinonaktifkan" in disable_resp.json()["message"]
