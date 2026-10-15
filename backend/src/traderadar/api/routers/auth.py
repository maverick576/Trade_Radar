"""Authentication router for login, logout, token refresh, password changes, and 2FA TOTP."""

from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import (
    get_client_ip,
    get_current_settings,
    get_current_user,
    get_db,
    get_redis_client,
    verify_csrf,
)
from traderadar.api.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    TotpDisableRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
    UserOut,
)
from traderadar.core.config import Settings
from traderadar.core.logging import get_logger
from traderadar.core.models import AuditLog, RefreshToken, User
from traderadar.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    check_login_rate_limit,
    clear_login_rate_limit,
    create_access_token,
    generate_csrf_token,
    generate_refresh_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    record_login_failure,
    verify_password,
    verify_totp_code,
)
from traderadar.core.time import utc_now

logger = get_logger("traderadar.api.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    cookie_secure: bool,
) -> None:
    """Set secure authentication cookies on the HTTP response."""
    # Access token cookie (short-lived)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        path="/",
    )
    # Refresh token cookie (long-lived, restricted path)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=cookie_secure,
        samesite="strict",
        path="/api/auth",
    )
    # CSRF cookie (readable by frontend JS for double-submit header)
    response.set_cookie(
        key="traderadar_csrf",
        value=csrf_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=False,
        secure=cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response, cookie_secure: bool) -> None:
    """Clear all authentication cookies on logout or session expiration."""
    response.delete_cookie(key="access_token", path="/", secure=cookie_secure, samesite="lax")
    response.delete_cookie(
        key="refresh_token", path="/api/auth", secure=cookie_secure, samesite="strict"
    )
    response.delete_cookie(key="traderadar_csrf", path="/", secure=cookie_secure, samesite="lax")


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_current_settings),
) -> LoginResponse:
    """Authenticate user with email and password, plus TOTP 2FA if enabled."""
    client_ip = get_client_ip(request)
    email_clean = payload.email.strip().lower()

    # 1. Rate-limit checks (per IP and per email)
    allowed_ip, wait_ip = await check_login_rate_limit(redis, client_ip)
    if not allowed_ip:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": (
                    f"Terlalu banyak percobaan login gagal dari IP Anda. Coba lagi dalam {wait_ip} "
                    "detik."
                ),
            },
        )

    allowed_email, wait_email = await check_login_rate_limit(redis, email_clean)
    if not allowed_email:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": (
                    "Akun terkunci sementara karena terlalu banyak percobaan. "
                    f"Coba lagi dalam {wait_email} detik."
                ),
            },
        )

    # 2. Look up user by email
    stmt = select(User).where(User.email == email_clean)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        await record_login_failure(redis, client_ip)
        await record_login_failure(redis, email_clean)
        audit = AuditLog(
            user_id=user.id if user else None,
            action="login_failed_password",
            detail={"email": email_clean},
            ip=client_ip,
        )
        db.add(audit)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Email atau kata sandi tidak valid."},
        )

    # 3. Check 2FA TOTP if configured
    if user.totp_secret:
        if not payload.totp_code:
            return LoginResponse(
                requires_2fa=True,
                message="Kode 2FA TOTP diperlukan untuk melanjutkan.",
                user=None,
                csrf_token=None,
            )

        if not verify_totp_code(user.totp_secret, payload.totp_code):
            await record_login_failure(redis, client_ip)
            audit = AuditLog(
                user_id=user.id,
                action="login_failed_totp",
                detail={"email": email_clean},
                ip=client_ip,
            )
            db.add(audit)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_TOTP",
                    "message": "Kode 2FA TOTP tidak valid atau telah kedaluwarsa.",
                },
            )

    # 4. Successful login: clear rate limits
    await clear_login_rate_limit(redis, client_ip)
    await clear_login_rate_limit(redis, email_clean)

    # 5. Update user last login
    now = utc_now()
    user.last_login_at = now

    # 6. Issue tokens
    raw_refresh, hashed_refresh = generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_record)

    access_token = create_access_token(user_id=user.id, email=user.email)
    csrf_token = generate_csrf_token()

    # 7. Audit log
    audit = AuditLog(
        user_id=user.id,
        action="login_success",
        detail={"email": email_clean},
        ip=client_ip,
    )
    db.add(audit)

    # 8. Set response cookies
    _set_auth_cookies(
        response=response,
        access_token=access_token,
        refresh_token=raw_refresh,
        csrf_token=csrf_token,
        cookie_secure=settings.env.COOKIE_SECURE,
    )

    user_out = UserOut(
        id=user.id,
        email=user.email,
        totp_enabled=bool(user.totp_secret),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )
    return LoginResponse(
        requires_2fa=False,
        message="Login berhasil.",
        user=user_out,
        csrf_token=csrf_token,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_current_settings),
) -> MessageResponse:
    """Log out current session, revoke refresh token, and clear auth cookies."""
    client_ip = get_client_ip(request)
    if refresh_token:
        hashed = hash_token(refresh_token)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token_hash == hashed, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
        await db.execute(stmt)

    audit = AuditLog(
        user_id=None,
        action="logout",
        detail={},
        ip=client_ip,
    )
    db.add(audit)

    _clear_auth_cookies(response, settings.env.COOKIE_SECURE)
    return MessageResponse(message="Berhasil keluar.")


@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_current_settings),
) -> dict[str, str]:
    """Rotate refresh token and issue new access token."""
    client_ip = get_client_ip(request)
    if not refresh_token:
        _clear_auth_cookies(response, settings.env.COOKIE_SECURE)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Refresh token tidak ditemukan. Silakan login kembali.",
            },
        )

    now = utc_now()
    hashed = hash_token(refresh_token)
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == hashed,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > now,
    )
    res = await db.execute(stmt)
    token_record = res.scalar_one_or_none()

    if not token_record:
        _clear_auth_cookies(response, settings.env.COOKIE_SECURE)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Sesi telah kedaluwarsa atau dicabut. Silakan login kembali.",
            },
        )

    # Fetch associated user
    user_stmt = select(User).where(User.id == token_record.user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user:
        _clear_auth_cookies(response, settings.env.COOKIE_SECURE)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Pengguna tidak ditemukan."},
        )

    # Revoke old refresh token (rotation)
    token_record.revoked_at = now

    # Create new tokens
    raw_refresh, new_hashed = generate_refresh_token()
    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=new_hashed,
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_token_record)

    new_access_token = create_access_token(user_id=user.id, email=user.email)
    new_csrf_token = generate_csrf_token()

    _set_auth_cookies(
        response=response,
        access_token=new_access_token,
        refresh_token=raw_refresh,
        csrf_token=new_csrf_token,
        cookie_secure=settings.env.COOKIE_SECURE,
    )

    audit = AuditLog(
        user_id=user.id,
        action="token_refreshed",
        detail={},
        ip=client_ip,
    )
    db.add(audit)

    return {"message": "Sesi berhasil diperbarui.", "csrf_token": new_csrf_token}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Get current authenticated user profile."""
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        totp_enabled=bool(current_user.totp_secret),
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
    )


@router.put("/password", response_model=MessageResponse, dependencies=[Depends(verify_csrf)])
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Change current user's password and revoke active refresh tokens."""
    client_ip = get_client_ip(request)
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PASSWORD", "message": "Kata sandi saat ini salah."},
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PASSWORD_TOO_SHORT", "message": "Kata sandi baru minimal 8 karakter."},
        )

    current_user.password_hash = hash_password(payload.new_password)

    # Revoke all existing refresh tokens for security
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await db.execute(stmt)

    audit = AuditLog(
        user_id=current_user.id,
        action="password_changed",
        detail={},
        ip=client_ip,
    )
    db.add(audit)

    return MessageResponse(
        message="Kata sandi berhasil diperbarui. Silakan login kembali pada perangkat lain."
    )


@router.post("/totp/setup", response_model=TotpSetupResponse, dependencies=[Depends(verify_csrf)])
async def setup_totp(
    current_user: User = Depends(get_current_user),
) -> TotpSetupResponse:
    """Generate a new TOTP secret and provisioning URI for setup."""
    secret = generate_totp_secret()
    otpauth_url = get_totp_uri(secret, current_user.email)
    return TotpSetupResponse(secret=secret, otpauth_url=otpauth_url)


@router.post("/totp/verify", response_model=MessageResponse, dependencies=[Depends(verify_csrf)])
async def verify_and_enable_totp(
    payload: TotpVerifyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify code from authenticator app and enable 2FA on the account."""
    client_ip = get_client_ip(request)
    if not verify_totp_code(payload.secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TOTP",
                "message": "Kode verifikasi 2FA tidak valid atau sudah kedaluwarsa.",
            },
        )

    current_user.totp_secret = payload.secret

    audit = AuditLog(
        user_id=current_user.id,
        action="totp_enabled",
        detail={},
        ip=client_ip,
    )
    db.add(audit)

    return MessageResponse(message="Autentikasi dua faktor (2FA) TOTP berhasil diaktifkan.")


@router.post("/totp/disable", response_model=MessageResponse, dependencies=[Depends(verify_csrf)])
async def disable_totp(
    payload: TotpDisableRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Disable 2FA TOTP after confirming password and current TOTP code."""
    client_ip = get_client_ip(request)
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TOTP_NOT_ENABLED", "message": "2FA TOTP belum aktif pada akun ini."},
        )

    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PASSWORD", "message": "Kata sandi salah."},
        )

    if not verify_totp_code(current_user.totp_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TOTP", "message": "Kode 2FA TOTP tidak valid."},
        )

    current_user.totp_secret = None

    audit = AuditLog(
        user_id=current_user.id,
        action="totp_disabled",
        detail={},
        ip=client_ip,
    )
    db.add(audit)

    return MessageResponse(message="2FA TOTP berhasil dinonaktifkan.")
