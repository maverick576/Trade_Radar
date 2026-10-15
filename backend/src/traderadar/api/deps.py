"""Dependencies for FastAPI routes including auth and security."""

from collections.abc import AsyncGenerator

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.core.config import Settings, get_settings
from traderadar.core.db import get_db_session
from traderadar.core.models import User
from traderadar.core.redis import get_redis
from traderadar.core.security import decode_access_token, verify_csrf_token


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


def get_client_ip(request: Request) -> str:
    """Extract client IP address respecting reverse proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate current authenticated user from cookie or Authorization header."""
    token: str | None = None
    if access_token:
        token = access_token
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Autentikasi diperlukan. Silakan login."},
        )

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Token tidak valid."},
            )
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": f"Sesi tidak valid atau telah kedaluwarsa: {exc}",
            },
        ) from exc

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Pengguna tidak ditemukan."},
        )

    return user


def verify_csrf(
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    traderadar_csrf: str | None = Cookie(default=None),
) -> None:
    """Verify CSRF token for state-mutating requests (POST, PUT, DELETE, PATCH)."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # If token in cookie or header is missing or does not match
        if not verify_csrf_token(traderadar_csrf, x_csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "CSRF_ERROR",
                    "message": "Token CSRF tidak valid atau tidak cocok.",
                },
            )
