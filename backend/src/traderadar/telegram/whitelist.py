"""Whitelist security and chat management for TradeRadar Telegram Bot.

Enforces strict access control via TELEGRAM_ALLOWED_CHAT_IDS (.env) and
persists chat authorization & pause preferences in postgres table `telegram_chats`.
"""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from traderadar.core.config import Settings, get_settings
from traderadar.core.db import get_db_session
from traderadar.core.logging import get_logger
from traderadar.core.models import TelegramChat
from traderadar.core.time import utc_now

logger = get_logger("traderadar.telegram.whitelist")


def get_allowed_chat_ids(settings: Settings | None = None) -> set[int]:
    """Parse comma-separated TELEGRAM_ALLOWED_CHAT_IDS from environment."""
    cfg = settings or get_settings()
    raw = cfg.env.TELEGRAM_ALLOWED_CHAT_IDS.strip()
    if not raw:
        return set()

    allowed: set[int] = set()
    for part in raw.split(","):
        clean = part.strip()
        if clean:
            try:
                allowed.add(int(clean))
            except ValueError:
                logger.warning("invalid_chat_id_in_env", item=clean)
    return allowed


def is_chat_allowed(chat_id: int, settings: Settings | None = None) -> bool:
    """Check if a Telegram chat ID is authorized."""
    allowed = get_allowed_chat_ids(settings)
    return chat_id in allowed


async def get_or_create_chat(
    session: AsyncSession,
    chat_id: int,
    username: str | None = None,
) -> TelegramChat:
    """Retrieve existing TelegramChat or register a new one."""
    stmt = select(TelegramChat).where(TelegramChat.chat_id == chat_id)
    chat = await session.scalar(stmt)
    if chat:
        if username and chat.username != username:
            chat.username = username
            await session.commit()
            await session.refresh(chat)
        return chat

    new_chat = TelegramChat(
        chat_id=chat_id,
        username=username,
        paused=False,
        created_at=utc_now(),
    )
    session.add(new_chat)
    await session.commit()
    await session.refresh(new_chat)
    return new_chat


async def is_chat_paused(session: AsyncSession, chat_id: int) -> bool:
    """Check if notifications are paused for this chat."""
    stmt = select(TelegramChat.paused).where(TelegramChat.chat_id == chat_id)
    paused = await session.scalar(stmt)
    return bool(paused)


async def set_chat_paused(session: AsyncSession, chat_id: int, paused: bool) -> bool:
    """Set notification pause preference for a chat."""
    stmt = select(TelegramChat).where(TelegramChat.chat_id == chat_id)
    chat = await session.scalar(stmt)
    if not chat:
        chat = TelegramChat(
            chat_id=chat_id,
            username=None,
            paused=paused,
            created_at=utc_now(),
        )
        session.add(chat)
    else:
        chat.paused = paused

    await session.commit()
    return paused


async def get_active_notification_chats(
    session: AsyncSession,
    settings: Settings | None = None,
) -> list[int]:
    """Retrieve all authorized chat IDs that have not paused notifications."""
    allowed = get_allowed_chat_ids(settings)
    if not allowed:
        return []

    stmt = select(TelegramChat).where(
        (TelegramChat.chat_id.in_(allowed)) & (TelegramChat.paused == False)  # noqa: E712
    )
    result = await session.execute(stmt)
    registered_chats = list(result.scalars().all())
    registered_ids = {c.chat_id for c in registered_chats}

    # Any allowed chats not yet in DB default to active
    active_ids = list(registered_ids)
    for cid in allowed:
        if cid not in registered_ids:
            # Check if recorded as paused
            paused = await is_chat_paused(session, cid)
            if not paused:
                active_ids.append(cid)

    return sorted(set(active_ids))


def whitelist_only(
    handler_func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]],
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """Decorator to restrict handler execution strictly to authorized Telegram chats."""

    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if not chat:
            return None

        if not is_chat_allowed(chat.id):
            logger.warning(
                "unauthorized_chat_ignored",
                chat_id=chat.id,
                username=update.effective_user.username if update.effective_user else None,
            )
            # ROADMAP criteria: "chat tak terdaftar diabaikan" -> completely ignored
            return None

        # Record or update chat in DB
        try:
            username = update.effective_user.username if update.effective_user else None
            async with get_db_session() as session:
                await get_or_create_chat(session, chat.id, username)
        except Exception as exc:
            logger.error("failed_to_register_chat", error=str(exc))

        await handler_func(update, context)
        return None

    return wrapper
