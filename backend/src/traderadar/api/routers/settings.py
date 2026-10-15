"""Settings and Telegram integration management endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.constants import ParseMode

from traderadar.api.deps import get_current_user, get_db
from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.core.models import User
from traderadar.telegram.bot import create_bot
from traderadar.telegram.whitelist import (
    get_active_notification_chats,
    get_allowed_chat_ids,
)

logger = get_logger("traderadar.api.settings")
router = APIRouter(prefix="/settings", tags=["settings"])


class TelegramStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    allowed_chat_ids_count: int
    active_chat_ids_count: int
    allowed_chat_ids: list[int]
    status: str


class TelegramTestMessageResponse(BaseModel):
    success: bool
    sent_count: int
    message: str


@router.get("", response_model=dict[str, Any])
async def get_app_settings(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Retrieve current application configuration settings."""
    settings = get_settings()
    return settings.app.model_dump(mode="json")


@router.get("/telegram/status", response_model=TelegramStatusResponse)
async def get_telegram_status(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramStatusResponse:
    """Check Telegram bot status, configuration, and subscriber counts."""
    settings = get_settings()
    enabled = settings.env.TELEGRAM_ENABLED
    configured = bool(settings.env.TELEGRAM_BOT_TOKEN)
    allowed_ids = list(get_allowed_chat_ids(settings))
    active_ids = await get_active_notification_chats(session, settings)

    bot_status = "disabled"
    if enabled:
        bot_status = "online" if configured else "unconfigured"

    return TelegramStatusResponse(
        enabled=enabled,
        configured=configured,
        allowed_chat_ids_count=len(allowed_ids),
        active_chat_ids_count=len(active_ids),
        allowed_chat_ids=allowed_ids,
        status=bot_status,
    )


@router.post("/telegram/test", response_model=TelegramTestMessageResponse)
async def send_telegram_test_message(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramTestMessageResponse:
    """Send a test message to all registered Telegram subscribers."""
    settings = get_settings()
    if not settings.env.TELEGRAM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot dinonaktifkan di konfigurasi (TELEGRAM_ENABLED=false).",
        )

    if not settings.env.TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TELEGRAM_BOT_TOKEN belum diisi di file .env.",
        )

    active_chats = await get_active_notification_chats(session, settings)
    if not active_chats:
        allowed = list(get_allowed_chat_ids(settings))
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Belum ada Chat ID yang terdaftar di TELEGRAM_ALLOWED_CHAT_IDS.",
            )
        active_chats = allowed

    bot_app = create_bot(settings)
    if not bot_app:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menginisialisasi instance Telegram Bot.",
        )

    test_text = (
        "🔔 *Uji Koneksi TradeRadar Telegram Bot*\n\n"
        "Halo! Ini adalah pesan uji dari panel Pengaturan TradeRadar.\n"
        "Status: *Berhasil Terhubung dan Siap Menerima Notifikasi.*"
    )

    sent = 0
    errors: list[str] = []
    for cid in active_chats:
        try:
            await bot_app.bot.send_message(
                chat_id=cid,
                text=test_text,
                parse_mode=ParseMode.MARKDOWN,
            )
            sent += 1
        except Exception as exc:
            errors.append(f"Chat {cid}: {exc}")

    if sent == 0 and errors:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal mengirim pesan uji ke Telegram: {'; '.join(errors)}",
        )

    return TelegramTestMessageResponse(
        success=True,
        sent_count=sent,
        message=f"Pesan uji berhasil dikirim ke {sent} penerima Telegram.",
    )
