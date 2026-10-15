"""Unit tests for core security, password hashing, JWT, CSRF, and TOTP."""

from datetime import timedelta

import jwt
import pyotp
import pytest

from traderadar.core.security import (
    create_access_token,
    decode_access_token,
    generate_csrf_token,
    generate_refresh_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    verify_csrf_token,
    verify_password,
    verify_totp_code,
)


def test_password_hashing() -> None:
    raw = "SuperSecretPassword123!"
    hashed = hash_password(raw)

    assert hashed != raw
    assert hashed.startswith("$argon2id$")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_token_creation_and_decoding() -> None:
    token = create_access_token(user_id=42, email="trader@example.com")
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["email"] == "trader@example.com"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_jwt_expired_token() -> None:
    # Expired token (in past)
    token = create_access_token(
        user_id=1, email="test@example.com", expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_invalid_signature() -> None:
    token = create_access_token(user_id=1, email="test@example.com")
    tampered_token = token[:-5] + "abcde"
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


def test_refresh_token_generation() -> None:
    raw, hashed = generate_refresh_token()
    assert len(raw) >= 40
    assert len(hashed) == 64  # SHA-256 hex string
    assert hash_token(raw) == hashed


def test_csrf_token_generation_and_verification() -> None:
    token = generate_csrf_token()
    assert len(token) >= 32
    assert verify_csrf_token(token, token) is True
    assert verify_csrf_token(token, "different_token") is False
    assert verify_csrf_token(None, token) is False
    assert verify_csrf_token(token, None) is False


def test_totp_secret_and_verification() -> None:
    secret = generate_totp_secret()
    assert len(secret) == 32

    uri = get_totp_uri(secret, "admin@example.com")
    assert "otpauth://totp/TradeRadar:" in uri
    assert "secret=" in uri

    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    assert verify_totp_code(secret, valid_code) is True
    assert verify_totp_code(secret, "000000") is False
