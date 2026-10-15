"""Security, password hashing, JWT, CSRF, TOTP, and rate-limiting utilities."""

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from redis.asyncio import Redis

from traderadar.core.config import get_settings
from traderadar.core.time import utc_now

# Argon2 Password Hasher instance
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900  # 15 minutes


def hash_password(plain_password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against Argon2 hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def hash_token(raw_token: str) -> str:
    """Hash opaque token with SHA-256 for safe database indexing and storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """Generate raw opaque refresh token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(48)
    return raw_token, hash_token(raw_token)


def generate_csrf_token() -> str:
    """Generate cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    """Verify double-submit CSRF cookie against request header using constant-time comparison."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def create_access_token(
    user_id: int,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create short-lived JWT access token."""
    settings = get_settings()
    now = utc_now()
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.env.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token.

    Raises jwt.PyJWTError on invalid or expired token.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.env.SECRET_KEY,
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Tipe token bukan token akses.")
    return payload


def generate_totp_secret() -> str:
    """Generate random base32 secret for TOTP."""
    return str(pyotp.random_base32())


def get_totp_uri(secret: str, email: str) -> str:
    """Get provisioning URI for authenticator apps (Google Authenticator, etc)."""
    totp = pyotp.TOTP(secret)
    return str(totp.provisioning_uri(name=email, issuer_name="TradeRadar"))


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify 6-digit TOTP code with time drift window."""
    totp = pyotp.TOTP(secret)
    # valid_window=1 allows +-30 seconds drift
    return bool(totp.verify(code.strip(), valid_window=1))


async def check_login_rate_limit(
    redis: Redis,
    identifier: str,
    max_attempts: int = LOGIN_MAX_ATTEMPTS,
    lockout_seconds: int = LOGIN_LOCKOUT_SECONDS,
) -> tuple[bool, int]:
    """Check if login attempt is allowed for given identifier (e.g. IP or email).

    Returns (is_allowed, remaining_seconds_if_locked).
    """
    key = f"ratelimit:login:{identifier}"
    count_str = await redis.get(key)
    if count_str is not None:
        count = int(count_str)
        if count >= max_attempts:
            ttl = await redis.ttl(key)
            return False, max(1, ttl)
    return True, 0


async def record_login_failure(
    redis: Redis,
    identifier: str,
    lockout_seconds: int = LOGIN_LOCKOUT_SECONDS,
) -> int:
    """Record a failed login attempt and increment counter.

    Returns the new attempt count.
    """
    key = f"ratelimit:login:{identifier}"
    pipeline = redis.pipeline()
    pipeline.incr(key)
    pipeline.expire(key, lockout_seconds)
    results = await pipeline.execute()
    return int(results[0])


async def clear_login_rate_limit(redis: Redis, identifier: str) -> None:
    """Clear failed login attempts counter on successful login."""
    key = f"ratelimit:login:{identifier}"
    await redis.delete(key)
