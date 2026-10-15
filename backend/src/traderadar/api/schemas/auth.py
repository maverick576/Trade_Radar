"""Pydantic schemas for authentication and authorization."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    """Public user profile schema."""

    id: int
    email: EmailStr
    totp_enabled: bool
    last_login_at: datetime | None = None
    created_at: datetime


class LoginRequest(BaseModel):
    """Login payload with optional TOTP code."""

    email: EmailStr
    password: str = Field(min_length=1)
    totp_code: str | None = Field(default=None, max_length=10)


class LoginResponse(BaseModel):
    """Successful login response."""

    requires_2fa: bool = False
    message: str = "Login berhasil."
    user: UserOut | None = None
    csrf_token: str | None = None


class MessageResponse(BaseModel):
    """Standard generic message response."""

    message: str
    detail: dict[str, str] | None = None


class ChangePasswordRequest(BaseModel):
    """Payload to update password."""

    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, description="Kata sandi baru minimal 8 karakter")


class TotpSetupResponse(BaseModel):
    """Response containing TOTP secret and otpauth URI."""

    secret: str
    otpauth_url: str


class TotpVerifyRequest(BaseModel):
    """Payload to verify and activate TOTP."""

    secret: str
    code: str = Field(min_length=6, max_length=8)


class TotpDisableRequest(BaseModel):
    """Payload to disable TOTP."""

    password: str = Field(min_length=1)
    code: str = Field(min_length=6, max_length=8)
